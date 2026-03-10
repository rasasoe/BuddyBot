#!/usr/bin/env python3
"""
Person Follower Node

Generates commands to follow detected person.
"""

import rclpy
from rclpy.node import Node

class PersonFollower(Node):
    def __init__(self):
        super().__init__('person_follower')
        # TODO: Implement person following
        pass

def main(args=None):
    rclpy.init(args=args)
    node = PersonFollower()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()