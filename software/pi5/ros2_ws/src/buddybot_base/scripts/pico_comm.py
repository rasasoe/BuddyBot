#!/usr/bin/env python3
"""
Pico Communication Node

Handles text-based UART communication with Raspberry Pi Pico.
Implements the line-based protocol specified in docs/uart_protocol.md
"""

import rclpy
from rclpy.node import Node
from buddybot_msgs.msg import Command, Status
import serial
import threading
import time
import re

class PicoComm(Node):
    def __init__(self):
        super().__init__('pico_comm')

        # Declare parameters
        self.declare_parameter('serial_port', '/dev/ttyAMA0')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('heartbeat_interval', 1.0)
        self.declare_parameter('status_timeout', 5.0)

        # Get parameters
        serial_port = self.get_parameter('serial_port').value
        baud_rate = self.get_parameter('baud_rate').value
        heartbeat_interval = self.get_parameter('heartbeat_interval').value
        self.status_timeout = self.get_parameter('status_timeout').value

        # Initialize serial connection
        try:
            self.serial = serial.Serial(serial_port, baud_rate, timeout=0.1)
            self.get_logger().info(f"Connected to Pico on {serial_port} at {baud_rate} baud")
        except serial.SerialException as e:
            self.get_logger().error(f"Failed to open serial port: {e}")
            raise

        # Publishers and subscribers
        self.cmd_sub = self.create_subscription(
            Command, 'cmd_vel', self.command_callback, 10)
        self.status_pub = self.create_publisher(Status, 'pico_status', 10)

        # Timers
        self.heartbeat_timer = self.create_timer(heartbeat_interval, self.send_heartbeat)
        self.status_check_timer = self.create_timer(0.1, self.check_status_timeout)

        # State variables
        self.last_status_time = time.time()
        self.emergency_stop = False
        self.current_mode = 'NORMAL'
        self.receive_thread = None
        self.running = True

        # Start receive thread
        self.receive_thread = threading.Thread(target=self.receive_loop)
        self.receive_thread.daemon = True
        self.receive_thread.start()

        self.get_logger().info("Pico communication node initialized")

    def command_callback(self, msg):
        """Handle velocity command messages"""
        try:
            # Send velocity command
            vx = max(-1.0, min(1.0, msg.linear_x))
            vy = max(-1.0, min(1.0, msg.linear_y))
            wz = max(-1.0, min(1.0, msg.angular_z))

            command = f"CMD,{vx:.3f},{vy:.3f},{wz:.3f}\n"
            self.serial.write(command.encode('utf-8'))
            self.get_logger().debug(f"Sent command: {command.strip()}")

        except Exception as e:
            self.get_logger().error(f"Failed to send command: {e}")

    def send_heartbeat(self):
        """Send heartbeat to Pico"""
        try:
            self.serial.write(b"HB\n")
            self.get_logger().debug("Sent heartbeat")
        except Exception as e:
            self.get_logger().error(f"Failed to send heartbeat: {e}")

    def send_brake(self):
        """Send emergency brake command"""
        try:
            self.serial.write(b"BRAKE\n")
            self.get_logger().info("Sent emergency brake")
        except Exception as e:
            self.get_logger().error(f"Failed to send brake: {e}")

    def send_clear(self):
        """Send clear emergency stop command"""
        try:
            self.serial.write(b"CLEAR\n")
            self.get_logger().info("Sent clear emergency stop")
        except Exception as e:
            self.get_logger().error(f"Failed to send clear: {e}")

    def send_mode(self, mode):
        """Send mode change command"""
        try:
            command = f"MODE,{mode}\n"
            self.serial.write(command.encode('utf-8'))
            self.get_logger().info(f"Sent mode change: {mode}")
        except Exception as e:
            self.get_logger().error(f"Failed to send mode: {e}")

    def receive_loop(self):
        """Background thread to receive messages from Pico"""
        buffer = ""
        while self.running:
            try:
                if self.serial.in_waiting:
                    data = self.serial.read(self.serial.in_waiting).decode('utf-8', errors='ignore')
                    buffer += data

                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        if line:
                            self.process_message(line)

                time.sleep(0.01)  # Small delay to prevent busy waiting

            except Exception as e:
                self.get_logger().error(f"Receive error: {e}")
                time.sleep(0.1)

    def process_message(self, line):
        """Process incoming message from Pico"""
        self.get_logger().debug(f"Received: {line}")

        try:
            parts = line.split(',')
            if not parts:
                return

            msg_type = parts[0].upper()

            if msg_type == 'ACK':
                # Acknowledgment
                if len(parts) >= 2:
                    ack_type = parts[1]
                    self.get_logger().debug(f"ACK received for: {ack_type}")

            elif msg_type == 'STAT':
                # Status report
                self.parse_status(parts[1:])

            elif msg_type == 'RPM':
                # RPM report
                self.parse_rpm(parts[1:])

            elif msg_type == 'SAFE':
                # Safety event
                if len(parts) >= 2:
                    reason = parts[1]
                    self.get_logger().warn(f"Safety event: {reason}")
                    if reason == 'brake_command':
                        self.emergency_stop = True

        except Exception as e:
            self.get_logger().error(f"Failed to process message '{line}': {e}")

    def parse_status(self, params):
        """Parse status message parameters"""
        status = Status()
        status.emergency_stop = self.emergency_stop
        status.mode = self.current_mode

        # Parse key=value pairs
        for param in params:
            if '=' in param:
                key, value = param.split('=', 1)
                key = key.lower()
                if key == 'estop':
                    status.emergency_stop = value == '1'
                    self.emergency_stop = status.emergency_stop
                elif key == 'timeout':
                    # Timeout status
                    pass
                elif key == 'mode':
                    status.mode = value
                    self.current_mode = value

        # Publish status
        self.status_pub.publish(status)
        self.last_status_time = time.time()
        self.get_logger().debug("Published status update")

    def parse_rpm(self, params):
        """Parse RPM message parameters"""
        # TODO: Add RPM fields to Status message if needed
        # For now, just log
        rpm_data = {}
        for param in params:
            if '=' in param:
                key, value = param.split('=', 1)
                rpm_data[key] = float(value) if '.' in value else int(value)

        self.get_logger().debug(f"RPM data: {rpm_data}")

    def check_status_timeout(self):
        """Check if status updates have timed out"""
        if time.time() - self.last_status_time > self.status_timeout:
            self.get_logger().warn("Status timeout - Pico may be unresponsive")
            # Could trigger safety measures here

    def destroy_node(self):
        """Clean shutdown"""
        self.running = False
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=1.0)

        if hasattr(self, 'serial') and self.serial.is_open:
            self.serial.close()

        super().destroy_node()

def main(args=None):
    rclpy.init(args=args)
    node = PicoComm()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()