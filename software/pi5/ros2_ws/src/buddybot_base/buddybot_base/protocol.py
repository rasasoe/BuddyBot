"""
BuddyBot UART Protocol Handler

This module handles the text-based UART communication protocol between
the Raspberry Pi 5 and Raspberry Pi Pico. The protocol is designed to be
human-readable for easy debugging and robust for safety-critical operations.

Protocol Overview:
- Text-based, line-delimited messages
- Key=value parameter format
- Commands from Pi 5 to Pico
- Responses from Pico to Pi 5
- Safety-first design with acknowledgments and status reporting

Architecture:
- Command parsing and validation
- Response formatting
- Error handling for malformed messages
- Type safety for velocity commands
"""

import re
from typing import Optional, Tuple, Dict, Any


class UARTProtocol:
    """
    Handles encoding/decoding of UART protocol messages.

    This class provides methods to:
    - Parse incoming command messages from Pi 5
    - Format outgoing response messages to Pi 5
    - Validate message formats and parameters
    - Handle protocol errors gracefully
    """

    # Message type constants
    MSG_HEARTBEAT = "HB"
    MSG_COMMAND = "CMD"
    MSG_BRAKE = "BRAKE"
    MSG_CLEAR = "CLEAR"
    MSG_MODE = "MODE"
    MSG_ACK = "ACK"
    MSG_STATUS = "STAT"
    MSG_RPM = "RPM"
    MSG_SAFETY = "SAFE"

    # Valid operating modes
    VALID_MODES = ["NORMAL", "SAFE", "MANUAL"]

    @staticmethod
    def parse_command(line: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Parse a command message from Pi 5.

        Args:
            line: Raw command line (without newline)

        Returns:
            Tuple of (command_type, parameters_dict) or None if invalid

        Examples:
            "HB" -> ("HB", {})
            "CMD,0.500,0.000,0.200" -> ("CMD", {"vx": 0.5, "vy": 0.0, "wz": 0.2})
            "MODE,NORMAL" -> ("MODE", {"mode": "NORMAL"})
        """
        if not line or not isinstance(line, str):
            return None

        line = line.strip()
        if not line:
            return None

        parts = line.split(',')
        if not parts:
            return None

        command = parts[0].upper()

        try:
            if command == UARTProtocol.MSG_HEARTBEAT:
                return UARTProtocol.MSG_HEARTBEAT, {}

            elif command == UARTProtocol.MSG_COMMAND and len(parts) == 4:
                # Parse velocity command: CMD,vx,vy,wz
                vx = float(parts[1])
                vy = float(parts[2])
                wz = float(parts[3])

                # Clamp to valid range [-1.0, 1.0]
                vx = max(-1.0, min(1.0, vx))
                vy = max(-1.0, min(1.0, vy))
                wz = max(-1.0, min(1.0, wz))

                return UARTProtocol.MSG_COMMAND, {
                    'vx': vx, 'vy': vy, 'wz': wz
                }

            elif command == UARTProtocol.MSG_BRAKE:
                return UARTProtocol.MSG_BRAKE, {}

            elif command == UARTProtocol.MSG_CLEAR:
                return UARTProtocol.MSG_CLEAR, {}

            elif command == UARTProtocol.MSG_MODE and len(parts) == 2:
                mode = parts[1].upper()
                if mode in UARTProtocol.VALID_MODES:
                    return UARTProtocol.MSG_MODE, {'mode': mode}
                else:
                    return None  # Invalid mode

            else:
                return None  # Unknown or malformed command

        except (ValueError, IndexError):
            # Invalid number format or wrong number of parameters
            return None

    @staticmethod
    def format_ack(command_type: str) -> str:
        """
        Format an acknowledgment response.

        Args:
            command_type: The command being acknowledged

        Returns:
            Formatted ACK message
        """
        return f"{UARTProtocol.MSG_ACK},{command_type}"

    @staticmethod
    def format_status(estop: bool, timeout: bool, mode: str) -> str:
        """
        Format a status response.

        Args:
            estop: Emergency stop active
            timeout: Watchdog timeout occurred
            mode: Current operating mode

        Returns:
            Formatted STAT message
        """
        estop_val = 1 if estop else 0
        timeout_val = 1 if timeout else 0
        return f"{UARTProtocol.MSG_STATUS},estop={estop_val},timeout={timeout_val},mode={mode}"

    @staticmethod
    def format_rpm(m1_rpm: float, m2_rpm: float, m3_rpm: float) -> str:
        """
        Format an RPM status response.

        Args:
            m1_rpm: Motor 1 RPM
            m2_rpm: Motor 2 RPM
            m3_rpm: Motor 3 RPM

        Returns:
            Formatted RPM message
        """
        return ".1f"

    @staticmethod
    def format_safety_event(reason: str) -> str:
        """
        Format a safety event message.

        Args:
            reason: Description of the safety event

        Returns:
            Formatted SAFE message
        """
        return f"{UARTProtocol.MSG_SAFETY},{reason}"

    @staticmethod
    def parse_status_response(line: str) -> Optional[Dict[str, Any]]:
        """
        Parse a status response from Pico.

        Args:
            line: Raw status line

        Returns:
            Dictionary with parsed status values or None if invalid

        Example:
            "STAT,estop=0,timeout=0,mode=NORMAL" ->
            {"estop": False, "timeout": False, "mode": "NORMAL"}
        """
        if not line.startswith(UARTProtocol.MSG_STATUS + ","):
            return None

        params = line[len(UARTProtocol.MSG_STATUS + ","):]
        result = {}

        for param in params.split(','):
            if '=' in param:
                key, value = param.split('=', 1)
                key = key.lower()

                if key in ['estop', 'timeout']:
                    result[key] = value == '1'
                elif key == 'mode':
                    result[key] = value.upper()

        return result if result else None

    @staticmethod
    def parse_rpm_response(line: str) -> Optional[Dict[str, float]]:
        """
        Parse an RPM response from Pico.

        Args:
            line: Raw RPM line

        Returns:
            Dictionary with motor RPMs or None if invalid

        Example:
            "RPM,m1=1200.5,m2=1150.2,m3=1180.8" ->
            {"m1": 1200.5, "m2": 1150.2, "m3": 1180.8}
        """
        if not line.startswith(UARTProtocol.MSG_RPM + ","):
            return None

        params = line[len(UARTProtocol.MSG_RPM + ","):]
        result = {}

        for param in params.split(','):
            if '=' in param:
                key, value = param.split('=', 1)
                try:
                    result[key] = float(value)
                except ValueError:
                    continue

        return result if result else None

    @staticmethod
    def format_command(vx: float, vy: float, wz: float) -> str:
        """
        Format a velocity command message.

        Args:
            vx: Linear velocity in X direction (-1.0 to 1.0)
            vy: Linear velocity in Y direction (-1.0 to 1.0)
            wz: Angular velocity (-1.0 to 1.0)

        Returns:
            Formatted CMD message
        """
        # Clamp values to valid range
        vx = max(-1.0, min(1.0, vx))
        vy = max(-1.0, min(1.0, vy))
        wz = max(-1.0, min(1.0, wz))

        return ".3f"

    @staticmethod
    def format_heartbeat() -> str:
        """
        Format a heartbeat message.

        Returns:
            Formatted HB message
        """
        return UARTProtocol.MSG_HEARTBEAT

    @staticmethod
    def parse_response(line: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Parse a response message from Pico.

        Args:
            line: Raw response line

        Returns:
            Tuple of (message_type, parameters_dict) or None if invalid
        """
        if not line or not isinstance(line, str):
            return None

        line = line.strip()
        if not line:
            return None

        parts = line.split(',', 1)
        if not parts:
            return None

        msg_type = parts[0].upper()

        try:
            if msg_type == UARTProtocol.MSG_ACK and len(parts) == 2:
                # ACK,command_type
                return UARTProtocol.MSG_ACK, {'command': parts[1]}

            elif msg_type == UARTProtocol.MSG_STATUS:
                # Parse status response
                status_params = UARTProtocol.parse_status_response(line)
                return (UARTProtocol.MSG_STATUS, status_params) if status_params else None

            elif msg_type == UARTProtocol.MSG_RPM:
                # Parse RPM response
                rpm_params = UARTProtocol.parse_rpm_response(line)
                return (UARTProtocol.MSG_RPM, rpm_params) if rpm_params else None

            elif msg_type == UARTProtocol.MSG_SAFETY:
                # Parse safety response
                reason = UARTProtocol.parse_safety_response(line)
                return (UARTProtocol.MSG_SAFETY, {'reason': reason}) if reason else None

            else:
                return None  # Unknown message type

        except (ValueError, IndexError):
            return None