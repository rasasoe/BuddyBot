#!/usr/bin/env python3
"""
Pico Communication Node

This node handles serial communication with the Raspberry Pi Pico (spinal cord).
It sends velocity commands and receives status updates, including emergency stop status.
Safety: This node monitors for Pico responses and can trigger system-wide alerts if communication fails.
"""

import rclpy
from rclpy.node import Node
from buddybot_msgs.msg import Command, Status
import serial
import struct
import time

class PicoComm(Node):
    def __init__(self):
        super().__init__('pico_comm')
        self.publisher = self.create_publisher(Status, 'pico_status', 10)
        self.subscription = self.create_subscription(
            Command,
            'velocity_command',
            self.command_callback,
            10)
        
        # Serial connection to Pico
        try:
            self.serial = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
            self.get_logger().info('Connected to Pico')
        except serial.SerialException as e:
            self.get_logger().error(f'Failed to connect to Pico: {e}')
            self.serial = None
        
        # Heartbeat timer
        self.timer = self.create_timer(0.1, self.timer_callback)  # 10Hz
        
        self.last_command_time = time.time()
        self.comm_timeout = 1.0  # seconds

    def command_callback(self, msg):
        if self.serial:
            # Pack command: linear_x, linear_y, angular_z as floats
            data = struct.pack('fff', msg.linear_x, msg.linear_y, msg.angular_z)
            try:
                self.serial.write(data)
                self.last_command_time = time.time()
            except serial.SerialException as e:
                self.get_logger().error(f'Failed to send command: {e}')

    def timer_callback(self):
        if self.serial:
            try:
                # Read status: battery, encoders, emergency_stop
                if self.serial.in_waiting >= 13:  # 4*3 + 1 bytes
                    data = self.serial.read(13)
                    battery, enc_l, enc_r, enc_b, emerg = struct.unpack('fiii?', data)
                    status = Status()
                    status.battery_voltage = battery
                    status.left_encoder = enc_l
                    status.right_encoder = enc_r
                    status.back_encoder = enc_b
                    status.emergency_stop = emerg
                    self.publisher.publish(status)
                else:
                    # Check for timeout
                    if time.time() - self.last_command_time > self.comm_timeout:
                        self.get_logger().warn('Communication timeout with Pico')
            except serial.SerialException as e:
                self.get_logger().error(f'Serial error: {e}')

def main(args=None):
    rclpy.init(args=args)
    node = PicoComm()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()