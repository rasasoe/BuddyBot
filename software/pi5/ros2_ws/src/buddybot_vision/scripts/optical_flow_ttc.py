#!/usr/bin/env python3
"""
Optical Flow TTC Node

Estimates time-to-collision using optical flow.
"""

import rclpy
from rclpy.node import Node

class OpticalFlowTTC(Node):
    def __init__(self):
        super().__init__('optical_flow_ttc')
        # TODO: Implement optical flow TTC
        pass

def main(args=None):
    rclpy.init(args=args)
    node = OpticalFlowTTC()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()