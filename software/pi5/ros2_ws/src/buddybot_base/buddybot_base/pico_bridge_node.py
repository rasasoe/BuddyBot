#!/usr/bin/env python3
"""
Pico Bridge Node for BuddyBot

This ROS 2 node serves as the communication bridge between the Raspberry Pi 5
and the Raspberry Pi Pico motor controller. It handles velocity commands,
heartbeat monitoring, and status reporting in a safety-critical manner.

Architecture Overview:
- Subscribes to velocity commands from the command multiplexer
- Converts ROS Twist messages to UART protocol commands
- Maintains heartbeat communication with Pico for watchdog functionality
- Publishes Pico status, safety events, and motor RPM data
- Automatically reconnects serial connection with exponential backoff
- Provides robust error handling and comprehensive logging

Safety Considerations:
- All velocity commands are clamped to safe ranges
- Emergency stop commands are handled immediately
- Serial communication errors trigger reconnection attempts
- Malformed messages are logged but don't crash the node
- Heartbeat failures are monitored and reported

Threading Model:
- Main thread: ROS 2 event loop, command processing
- Background thread: Serial communication and reconnection
- Thread-safe message passing between components
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from geometry_msgs.msg import Twist
from buddybot_msgs.msg import Status
from std_msgs.msg import String, Float32MultiArray
import time
import logging
import glob
from pathlib import Path
import serial

from .protocol import UARTProtocol
from .serial_manager import SerialManager


class PicoBridgeNode(Node):
    """
    ROS 2 node for Pico communication bridge.

    This node acts as the central communication hub between the high-level
    ROS 2 control systems and the low-level Pico motor controller.
    """

    def __init__(self):
        super().__init__('pico_bridge_node')

        # Declare parameters with defaults
        self.declare_parameter('serial_port', '/dev/ttyACM0')
        self.declare_parameter('serial_baudrate', 115200)
        self.declare_parameter('heartbeat_interval', 1.0)
        self.declare_parameter('status_timeout', 5.0)
        self.declare_parameter('max_reconnect_attempts', 10)
        self.declare_parameter('cmd_vel_timeout', 0.5)

        # Get parameters
        self.serial_port = self.get_parameter('serial_port').value
        self.serial_baudrate = self.get_parameter('serial_baudrate').value
        self.heartbeat_interval = self.get_parameter('heartbeat_interval').value
        self.status_timeout = self.get_parameter('status_timeout').value
        self.max_reconnect_attempts = self.get_parameter('max_reconnect_attempts').value
        self.cmd_vel_timeout = self.get_parameter('cmd_vel_timeout').value

        # Initialize components
        self.protocol = UARTProtocol()
        self.connected_port = self.serial_port
        self.serial_manager = SerialManager(
            port=self.connected_port,
            baudrate=self.serial_baudrate,
            max_reconnect_attempts=self.max_reconnect_attempts
        )

        # Set up serial receive callback
        self.serial_manager.set_receive_callback(self._handle_serial_message)

        # ROS 2 publishers with appropriate QoS
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            depth=10
        )

        self.status_publisher = self.create_publisher(
            Status, '/buddybot/pico_status', qos_profile)
        self.safety_publisher = self.create_publisher(
            String, '/buddybot/pico_safety_event', qos_profile)
        self.rpm_publisher = self.create_publisher(
            Float32MultiArray, '/buddybot/pico_rpm', qos_profile)

        # ROS 2 subscriber
        self.cmd_vel_subscriber = self.create_subscription(
            Twist, '/cmd_vel_final', self._cmd_vel_callback, 10)

        # Timers
        self.heartbeat_timer = self.create_timer(
            self.heartbeat_interval, self._send_heartbeat)
        self.status_check_timer = self.create_timer(
            0.1, self._check_status_timeout)
        self.reconnect_timer = self.create_timer(
            2.0, self._reconnect_if_needed)

        # State tracking
        self.last_cmd_vel_time = time.time()
        self.last_status_time = time.time()
        self.current_mode = 'NORMAL'
        self.emergency_stop_active = False
        self.legacy_protocol_detected = False

        # Connect to Pico
        selected_port = self._connect_serial_with_fallback()
        if selected_port:
            self.connected_port = selected_port
            self.serial_manager.port = selected_port
            self.get_logger().info(f"Connected to Pico serial device {selected_port}")
            self.serial_manager.start_receive_thread()
        else:
            self.get_logger().error("Failed to connect to Pico on startup; receive loop will retry using SerialManager backoff")

        self.get_logger().info("Pico Bridge Node initialized")
        self._log_startup_info()

    def _log_startup_info(self):
        """Log startup configuration for debugging."""
        self.get_logger().info("Configuration:")
        self.get_logger().info(f"  Serial port: {self.serial_port}")
        self.get_logger().info(f"  Connected port: {self.connected_port}")
        self.get_logger().info(f"  Baud rate: {self.serial_baudrate}")
        self.get_logger().info(f"  Heartbeat interval: {self.heartbeat_interval}s")
        self.get_logger().info(f"  Status timeout: {self.status_timeout}s")
        self.get_logger().info(f"  Max reconnect attempts: {self.max_reconnect_attempts}")
        self.get_logger().info(f"  Command timeout: {self.cmd_vel_timeout}s")

    def _cmd_vel_callback(self, msg: Twist) -> None:
        """
        Handle incoming velocity commands.

        Converts ROS Twist messages to UART protocol commands and sends
        them to the Pico. Includes safety clamping and timeout tracking.

        Args:
            msg: ROS Twist message with linear and angular velocities
        """
        try:
            # Extract and clamp velocities
            vx = max(-1.0, min(1.0, msg.linear.x))
            vy = max(-1.0, min(1.0, msg.linear.y))
            wz = max(-1.0, min(1.0, msg.angular.z))

            # Send command via UART
            command = self.protocol.format_command(vx, vy, wz)
            if self.legacy_protocol_detected:
                command = f"{vx:.3f},{vy:.3f},{wz * 57.2958:.2f}"
            if self.serial_manager.send_message(command):
                self.last_cmd_vel_time = time.time()
                self.get_logger().debug(f"Sent velocity command: vx={vx:.3f}, vy={vy:.3f}, wz={wz:.3f}")
            else:
                self.get_logger().warn("Failed to send velocity command - serial disconnected")

        except Exception as e:
            self.get_logger().error(f"Error processing velocity command: {e}")

    def _send_heartbeat(self) -> None:
        """
        Send periodic heartbeat to Pico.

        The heartbeat serves multiple purposes:
        1. Keeps the Pico watchdog alive
        2. Verifies serial connection health
        3. Provides timing reference for Pico
        """
        try:
            heartbeat_msg = self.protocol.format_heartbeat()
            if self.serial_manager.send_message(heartbeat_msg):
                self.get_logger().info("Heartbeat active")
            else:
                self.get_logger().warn("Failed to send heartbeat - serial disconnected")

        except Exception as e:
            self.get_logger().error(f"Error sending heartbeat: {e}")

    def _handle_serial_message(self, line: str) -> None:
        """
        Process incoming message from Pico.

        Parses the message according to the UART protocol and publishes
        appropriate ROS topics. Handles malformed messages gracefully.

        Args:
            line: Raw message line from Pico
        """
        try:
            self.get_logger().debug(f"Received from Pico: {line}")

            if line.startswith("FEEDBACK:"):
                self.legacy_protocol_detected = True
                self._handle_legacy_feedback(line)
                return

            # Parse the message
            parsed = self.protocol.parse_response(line)
            if not parsed:
                self.get_logger().warn(f"Ignoring malformed message: {line}")
                return

            msg_type, params = parsed

            if msg_type == UARTProtocol.MSG_ACK:
                # Acknowledgment - just log for now
                self.get_logger().debug(f"ACK received for: {params.get('command', 'unknown')}")

            elif msg_type == UARTProtocol.MSG_STATUS:
                # Status update - publish to ROS
                self._publish_status(params)

            elif msg_type == UARTProtocol.MSG_RPM:
                # RPM data - publish to ROS
                self._publish_rpm(params)

            elif msg_type == UARTProtocol.MSG_SAFETY:
                # Safety event - publish to ROS
                self._publish_safety_event(params)

            else:
                self.get_logger().warn(f"Unknown message type: {msg_type}")

        except Exception as e:
            self.get_logger().error(f"Error processing serial message '{line}': {e}")

    def _handle_legacy_feedback(self, line: str) -> None:
        try:
            payload = line.split(":", 1)[1]
            parts = [float(item) for item in payload.split(",")]
            while len(parts) < 3:
                parts.append(0.0)

            self.last_status_time = time.time()
            self.current_mode = "LEGACY"

            self._publish_status({"estop": False, "mode": "LEGACY"})
            self._publish_rpm({"m0": parts[0], "m1": parts[1], "m2": parts[2]})
        except Exception as e:
            self.get_logger().warn(f"Failed to parse legacy FEEDBACK line '{line}': {e}")

    def _publish_status(self, params: dict) -> None:
        """
        Publish Pico status to ROS topic.

        Args:
            params: Parsed status parameters
        """
        try:
            status_msg = Status()
            status_msg.battery_voltage = float(params.get('battery_voltage', 0.0))
            status_msg.emergency_stop = params.get('estop', False)
            status_msg.mode = params.get('mode', 'UNKNOWN')

            # Update internal state
            self.emergency_stop_active = status_msg.emergency_stop
            self.current_mode = status_msg.mode
            self.last_status_time = time.time()

            self.status_publisher.publish(status_msg)
            self.get_logger().debug("Published Pico status")

        except Exception as e:
            self.get_logger().error(f"Error publishing status: {e}")

    def _publish_rpm(self, params: dict) -> None:
        """
        Publish motor RPM data to ROS topic.

        Args:
            params: Parsed RPM parameters
        """
        try:
            rpm_msg = Float32MultiArray()
            rpm_msg.data = [
                params.get('m0', 0.0),
                params.get('m1', 0.0),
                params.get('m2', 0.0)
            ]

            self.rpm_publisher.publish(rpm_msg)
            self.get_logger().debug(f"Published RPM data: {rpm_msg.data}")

        except Exception as e:
            self.get_logger().error(f"Error publishing RPM data: {e}")

    def _publish_safety_event(self, params: dict) -> None:
        """
        Publish safety event to ROS topic.

        Args:
            params: Parsed safety event parameters
        """
        try:
            reason = params.get('reason', 'unknown')
            safety_msg = String()
            safety_msg.data = reason

            self.safety_publisher.publish(safety_msg)
            self.get_logger().warn(f"Published safety event: {reason}")

        except Exception as e:
            self.get_logger().error(f"Error publishing safety event: {e}")

    def _check_status_timeout(self) -> None:
        """
        Check for Pico status timeout.

        If we haven't received a status update recently, log a warning.
        This helps detect Pico communication issues.
        """
        time_since_last_status = time.time() - self.last_status_time
        if time_since_last_status > self.status_timeout:
            self.get_logger().warn(f"No Pico status for {time_since_last_status:.1f}s")

    def _candidate_serial_ports(self):
        ports = [self.serial_port]
        ports.extend(sorted(glob.glob("/dev/ttyACM*")))
        ports.extend(sorted(glob.glob("/dev/ttyUSB*")))
        unique = []
        for port in ports:
            if port not in unique:
                unique.append(port)
        return unique

    def _probe_pico_port(self, port: str) -> bool:
        try:
            with serial.Serial(port=port, baudrate=self.serial_baudrate, timeout=0.25, write_timeout=0.5) as ser:
                time.sleep(0.15)
                ser.reset_input_buffer()
                ser.write(b"HB\n")
                ser.flush()
                deadline = time.time() + 0.8
                while time.time() < deadline:
                    raw = ser.readline()
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    if line.startswith("FEEDBACK:") or line.startswith("ACK") or line.startswith("STAT") or line.startswith("RPM"):
                        self.get_logger().info(f"Detected Pico-compatible device on {port} via '{line}'")
                        return True
        except Exception as e:
            self.get_logger().debug(f"Probe failed for {port}: {e}")
        return False

    def _connect_serial_with_fallback(self):
        probed_matches = []
        for port in self._candidate_serial_ports():
            if not Path(port).exists():
                continue
            if self._probe_pico_port(port):
                probed_matches.append(port)

        for port in probed_matches:
            self.serial_manager.port = port
            if self.serial_manager.connect():
                return port

        for port in self._candidate_serial_ports():
            if not Path(port).exists():
                continue
            self.serial_manager.port = port
            if self.serial_manager.connect():
                return port
        return None

    def _reconnect_if_needed(self) -> None:
        if self.serial_manager.is_connected():
            return
        selected_port = self._connect_serial_with_fallback()
        if selected_port:
            self.connected_port = selected_port
            self.serial_manager.port = selected_port
            self.serial_manager.start_receive_thread()
            self.get_logger().info(f"Recovered Pico connection on {selected_port}")

    def destroy_node(self):
        """Clean shutdown of the node."""
        self.get_logger().info("Shutting down Pico Bridge Node")

        # Stop serial communication
        self.serial_manager.stop_receive_thread()
        self.serial_manager.disconnect()

        # Call parent destroy
        super().destroy_node()


def main(args=None):
    """Main entry point for the Pico Bridge Node."""
    rclpy.init(args=args)

    node = None
    try:
        node = PicoBridgeNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        logging.error(f"Fatal error in Pico Bridge Node: {e}")
    finally:
        if node is not None:
            try:
                node.destroy_node()
            except Exception:
                pass
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
