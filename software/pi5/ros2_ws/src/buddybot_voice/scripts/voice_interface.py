#!/usr/bin/env python3
"""
Voice Interface Node

Handles wake word detection and voice commands.
"""

import rclpy
from rclpy.node import Node

class VoiceInterface(Node):
    def __init__(self):
        super().__init__('voice_interface')
        # TODO: Implement voice interface
        pass

def main(args=None):
    rclpy.init(args=args)
    node = VoiceInterface()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()