#!/usr/bin/env python3
"""
Person Detector Node

Detects persons in camera feed.
"""

import rclpy
from rclpy.node import Node

class PersonDetector(Node):
    def __init__(self):
        super().__init__('person_detector')
        # TODO: Implement person detection
        pass

def main(args=None):
    rclpy.init(args=args)
    node = PersonDetector()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()