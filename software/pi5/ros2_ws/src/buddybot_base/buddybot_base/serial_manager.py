"""
Serial Communication Manager for BuddyBot Pico

This module manages the serial connection to the Raspberry Pi Pico,
providing robust communication with automatic reconnection and error handling.

Architecture:
- Thread-safe serial operations
- Exponential backoff for reconnection attempts
- Connection health monitoring
- Graceful error handling and logging
- Non-blocking read operations

Key Features:
- Automatic reconnection on connection loss
- Configurable retry parameters
- Connection status monitoring
- Thread-safe message sending/receiving
"""

import serial
import time
import threading
from typing import Optional, Callable, List
import logging


class SerialManager:
    """
    Manages serial communication with the Pico.

    This class handles:
    - Establishing and maintaining serial connection
    - Automatic reconnection with exponential backoff
    - Thread-safe message sending and receiving
    - Connection health monitoring
    - Error handling and logging
    """

    def __init__(self,
                 port: str = '/dev/ttyACM0',
                 baudrate: int = 115200,
                 timeout: float = 0.1,
                 max_reconnect_attempts: int = 10,
                 base_reconnect_delay: float = 1.0,
                 max_reconnect_delay: float = 30.0):
        """
        Initialize the serial manager.

        Args:
            port: Serial port device path
            baudrate: Serial communication baud rate
            timeout: Serial read timeout in seconds
            max_reconnect_attempts: Maximum number of reconnection attempts
            base_reconnect_delay: Base delay between reconnection attempts
            max_reconnect_delay: Maximum delay between reconnection attempts
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.max_reconnect_attempts = max_reconnect_attempts
        self.base_reconnect_delay = base_reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay

        self.serial: Optional[serial.Serial] = None
        self.connected = False
        self.reconnect_attempt = 0
        self.last_connect_time = 0
        self.logger = logging.getLogger(__name__)

        # Thread safety
        self.lock = threading.RLock()
        self._stop_event = threading.Event()

        # Message buffers
        self.receive_buffer = ""
        self.send_queue: List[str] = []
        self.receive_callback: Optional[Callable[[str], None]] = None

    def set_receive_callback(self, callback: Callable[[str], None]) -> None:
        """
        Set callback for received messages.

        Args:
            callback: Function to call when a complete message is received
        """
        self.receive_callback = callback

    def connect(self) -> bool:
        """
        Establish serial connection.

        Returns:
            True if connection successful, False otherwise
        """
        with self.lock:
            try:
                if self.serial and self.serial.is_open:
                    self.serial.close()

                self.serial = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                    write_timeout=1.0
                )

                # Test the connection
                self.serial.flush()
                self.connected = True
                self.reconnect_attempt = 0
                self.last_connect_time = time.time()

                self.logger.info(f"Connected to Pico on {self.port} at {self.baudrate} baud")
                return True

            except (serial.SerialException, OSError) as e:
                self.connected = False
                if self.serial:
                    self.serial.close()
                    self.serial = None

                self.logger.error(f"Failed to connect to {self.port}: {e}")
                return False

    def disconnect(self) -> None:
        """Disconnect from serial port."""
        with self.lock:
            self._stop_event.set()
            self.connected = False

            if self.serial and self.serial.is_open:
                try:
                    self.serial.close()
                except Exception as e:
                    self.logger.error(f"Error closing serial connection: {e}")

            self.serial = None
            self.logger.info("Disconnected from Pico")

    def is_connected(self) -> bool:
        """
        Check if serial connection is active.

        Returns:
            True if connected and healthy, False otherwise
        """
        with self.lock:
            if not self.serial or not self.serial.is_open:
                return False

            # Additional health check - try to read (non-blocking)
            try:
                if self.serial.in_waiting:
                    return True
                # Could add more sophisticated health checks here
                return True
            except (serial.SerialException, OSError):
                self.connected = False
                return False

    def send_message(self, message: str) -> bool:
        """
        Send a message to the Pico.

        Args:
            message: Message to send (will be terminated with newline)

        Returns:
            True if sent successfully, False otherwise
        """
        with self.lock:
            if not self.is_connected():
                self.logger.warning("Cannot send message: not connected")
                return False

            try:
                full_message = message + '\n'
                self.serial.write(full_message.encode('utf-8'))
                self.serial.flush()  # Ensure message is sent
                self.logger.debug(f"Sent: {message}")
                return True

            except (serial.SerialException, OSError) as e:
                self.logger.error(f"Failed to send message '{message}': {e}")
                self.connected = False
                return False

    def _calculate_reconnect_delay(self) -> float:
        """
        Calculate delay for next reconnection attempt using exponential backoff.

        Returns:
            Delay in seconds
        """
        delay = self.base_reconnect_delay * (2 ** self.reconnect_attempt)
        return min(delay, self.max_reconnect_delay)

    def _attempt_reconnection(self) -> bool:
        """
        Attempt to reconnect to the Pico with backoff logic.

        Returns:
            True if reconnected successfully, False otherwise
        """
        if self.reconnect_attempt >= self.max_reconnect_attempts:
            self.logger.error(f"Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            return False

        delay = self._calculate_reconnect_delay()
        self.logger.info(f"Attempting reconnection in {delay:.1f} seconds (attempt {self.reconnect_attempt + 1})")

        time.sleep(delay)
        self.reconnect_attempt += 1

        if self.connect():
            self.logger.info("Successfully reconnected to Pico")
            return True
        else:
            return False

    def _process_received_data(self, data: str) -> None:
        """
        Process received data, extracting complete messages.

        Args:
            data: Raw received data
        """
        self.receive_buffer += data

        # Process complete lines
        while '\n' in self.receive_buffer:
            line, self.receive_buffer = self.receive_buffer.split('\n', 1)
            line = line.strip()

            if line and self.receive_callback:
                try:
                    self.receive_callback(line)
                except Exception as e:
                    self.logger.error(f"Error in receive callback for line '{line}': {e}")

    def _receive_loop(self) -> None:
        """Background thread for receiving data from Pico."""
        while not self._stop_event.is_set():
            try:
                if self.is_connected() and self.serial.in_waiting:
                    data = self.serial.read(self.serial.in_waiting).decode('utf-8', errors='ignore')
                    if data:
                        self._process_received_data(data)
                else:
                    time.sleep(0.01)  # Small delay when no data

            except (serial.SerialException, OSError) as e:
                self.logger.error(f"Serial receive error: {e}")
                self.connected = False

                # Attempt reconnection
                if not self._attempt_reconnection():
                    self.logger.error("Failed to reconnect, stopping receive loop")
                    break

            except Exception as e:
                self.logger.error(f"Unexpected error in receive loop: {e}")
                time.sleep(0.1)

    def start_receive_thread(self) -> None:
        """Start the background receive thread."""
        self._stop_event.clear()
        receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        receive_thread.start()
        self.logger.info("Started serial receive thread")

    def stop_receive_thread(self) -> None:
        """Stop the background receive thread."""
        self._stop_event.set()

    def get_connection_info(self) -> dict:
        """
        Get information about the current connection status.

        Returns:
            Dictionary with connection information
        """
        return {
            'connected': self.connected,
            'port': self.port,
            'baudrate': self.baudrate,
            'reconnect_attempts': self.reconnect_attempt,
            'last_connect_time': self.last_connect_time,
            'uptime': time.time() - self.last_connect_time if self.connected else 0
        }