#!/usr/bin/env python3
"""
Pico Communication Node

Handles serial communication with Raspberry Pi Pico.
Sends velocity commands and receives status updates.
"""

import rclpy
from rclpy.node import Node
from buddybot_msgs.msg import Command, Status
import serial
import struct

class PicoComm(Node):
    def __init__(self):
        super().__init__('pico_comm')
        # TODO: Implement serial comm with Pico
        pass

def main(args=None):
    rclpy.init(args=args)
    node = PicoComm()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()