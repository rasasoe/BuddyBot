"""
BuddyBot UART Protocol

This module handles UART communication with the Raspberry Pi 5.
Parses velocity commands and sends status packets.
"""

import machine
import struct
from config import UART_ID, UART_BAUDRATE, UART_TX_PIN, UART_RX_PIN

class UARTProtocol:
    def __init__(self):
        self.uart = machine.UART(UART_ID, baudrate=UART_BAUDRATE,
                                tx=machine.Pin(UART_TX_PIN),
                                rx=machine.Pin(UART_RX_PIN))
        self.last_command_time = 0

    def parse_command(self):
        """
        Parse incoming velocity command from Pi 5
        Returns: (vx, vy, wz) or None if no valid command
        """
        if self.uart.any() >= 12:  # 3 floats = 12 bytes
            try:
                data = self.uart.read(12)
                vx, vy, wz = struct.unpack('fff', data)
                self.last_command_time = machine.time_pulse_us(machine.Pin(0), 1) // 1000  # Approximate ms
                return vx, vy, wz
            except (struct.error, OSError):
                # Malformed packet - ignore and continue
                return None
        return None

    def send_status(self, battery_voltage, encoder_counts, emergency_stop):
        """
        Send status packet to Pi 5
        battery_voltage: float
        encoder_counts: dict of encoder counts
        emergency_stop: bool
        """
        try:
            data = struct.pack('fiii?',
                              battery_voltage,
                              encoder_counts.get('left', 0),
                              encoder_counts.get('right', 0),
                              encoder_counts.get('back', 0),
                              emergency_stop)
            self.uart.write(data)
        except OSError:
            # UART write failed - could log this
            pass

    def get_last_command_time(self):
        """Get timestamp of last valid command (ms)"""
        return self.last_command_time

# Create UART protocol instance
uart_protocol = UARTProtocol()