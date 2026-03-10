"""
BuddyBot USB Serial Protocol

This module handles text-based USB serial communication with the Raspberry Pi 5.
Implements the line-based protocol specified in docs/uart_protocol.md
Uses USB CDC serial interface instead of GPIO UART.
"""

import sys
import select
from config import UART_BAUDRATE

class UARTProtocol:
    def __init__(self):
        # Use USB serial via stdin/stdout instead of GPIO UART
        self.buffer = ""
        self.last_command_time = 0

    def _send_message(self, message):
        """Send a message with newline via USB serial"""
        try:
            print(message)  # USB serial output
        except:
            pass  # USB serial write failed

    def send_ack(self, command_type):
        """Send acknowledgment for a command"""
        self._send_message(f"ACK,{command_type}")

    def send_status(self, estop, timeout, mode):
        """Send status report"""
        self._send_message(f"STAT,estop={1 if estop else 0},timeout={1 if timeout else 0},mode={mode}")

    def send_rpm(self, m1_rpm, m2_rpm, m3_rpm):
        """Send motor RPM summary"""
        self._send_message(f"RPM,m1={m1_rpm},m2={m3_rpm},m3={m3_rpm}")

    def send_safety_event(self, reason):
        """Send safety event"""
        self._send_message(f"SAFE,{reason}")

    def _parse_command(self, line):
        """
        Parse a command line
        Returns: (command_type, params_dict) or (None, None) if invalid
        """
        line = line.strip()
        if not line:
            return None, None

    def send_ack(self, command_type):
        """Send acknowledgment for a command"""
        self._send_message(f"ACK,{command_type}")

    def send_status(self, estop, timeout, mode):
        """Send status report"""
        self._send_message(f"STAT,estop={1 if estop else 0},timeout={1 if timeout else 0},mode={mode}")

    def send_rpm(self, m1_rpm, m2_rpm, m3_rpm):
        """Send motor RPM summary"""
        self._send_message(f"RPM,m1={m1_rpm},m2={m2_rpm},m3={m3_rpm}")

    def send_safety_event(self, reason):
        """Send safety event"""
        self._send_message(f"SAFE,{reason}")

    def _parse_command(self, line):
        """
        Parse a command line
        Returns: (command_type, params_dict) or (None, None) if invalid
        """
        line = line.strip()
        if not line:
            return None, None

        parts = line.split(',')
        if not parts:
            return None, None

        command = parts[0].upper()

        # Parse parameters based on command type
        if command == 'HB':
            return 'HB', {}
        elif command == 'CMD' and len(parts) == 4:
            try:
                vx = float(parts[1])
                vy = float(parts[2])
                wz = float(parts[3])
                # Clamp to valid range
                vx = max(-1.0, min(1.0, vx))
                vy = max(-1.0, min(1.0, vy))
                wz = max(-1.0, min(1.0, wz))
                return 'CMD', {'vx': vx, 'vy': vy, 'wz': wz}
            except ValueError:
                return None, None
        elif command == 'BRAKE':
            return 'BRAKE', {}
        elif command == 'CLEAR':
            return 'CLEAR', {}
        elif command == 'MODE' and len(parts) == 2:
            mode = parts[1].upper()
            return 'MODE', {'mode': mode}
        else:
            return None, None

    def parse_command(self):
        """
        Check for and parse incoming command via USB serial
        Returns: (command_type, params_dict) or (None, None)
        """
        import utime

        # Check if data is available on USB serial (stdin)
        try:
            # Use select to check if data is available without blocking
            import select
            if select.select([sys.stdin], [], [], 0)[0]:
                # Read available data
                while True:
                    try:
                        char = sys.stdin.read(1)
                        if not char:  # No more data
                            break
                        if char == '\n':
                            # Process complete line
                            command_type, params = self._parse_command(self.buffer)
                            self.buffer = ""
                            if command_type:
                                self.last_command_time = utime.ticks_ms()
                                return command_type, params
                        else:
                            self.buffer += char
                            # Prevent buffer overflow
                            if len(self.buffer) > 64:
                                self.buffer = ""
                    except:
                        # Read error
                        self.buffer = ""
                        break
        except:
            # select not available or other error
            pass

        return None, None

    def get_last_command_time(self):
        """Get timestamp of last valid command (ms)"""
        return self.last_command_time

# Create UART protocol instance
uart_protocol = UARTProtocol()