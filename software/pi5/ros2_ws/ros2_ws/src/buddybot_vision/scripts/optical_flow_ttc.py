#!/usr/bin/env python3
"""
Optical Flow TTC Node

This node uses optical flow to estimate time-to-collision (TTC) from camera feed.
If TTC is below threshold, it triggers emergency stop.
Safety: Provides local collision avoidance independent of LiDAR.
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from buddybot_msgs.msg import Command
from cv_bridge import CvBridge
import cv2
import numpy as np

class OpticalFlowTTC(Node):
    def __init__(self):
        super().__init__('optical_flow_ttc')
        self.subscription = self.create_subscription(
            Image, 'camera/image_raw', self.image_callback, 10)
        self.publisher = self.create_publisher(Command, 'emergency_stop', 10)
        
        self.bridge = CvBridge()
        self.prev_frame = None
        self.lk_params = dict(winSize=(15,15), maxLevel=2,
                              criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03))
        
        self.ttc_threshold = 2.0  # seconds

    def image_callback(self, msg):
        cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='mono8')
        
        if self.prev_frame is None:
            self.prev_frame = cv_image
            return
        
        # Calculate optical flow
        flow = cv2.calcOpticalFlowFarneback(self.prev_frame, cv_image, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        
        # Estimate TTC from flow divergence
        # Simple approximation: average flow magnitude towards center
        h, w = flow.shape[:2]
        center_flow = flow[h//2-50:h//2+50, w//2-50:w//2+50]
        magnitude = np.sqrt(center_flow[...,0]**2 + center_flow[...,1]**2)
        avg_magnitude = np.mean(magnitude)
        
        # Rough TTC estimate (this is simplified)
        if avg_magnitude > 5.0:  # Threshold for significant motion
            ttc = 1.0 / avg_magnitude  # Inverse relationship
            if ttc < self.ttc_threshold:
                self.get_logger().warn(f'TTC too low: {ttc}')
                # Trigger emergency stop
                stop_cmd = Command()
                stop_cmd.linear_x = 0.0
                stop_cmd.linear_y = 0.0
                stop_cmd.angular_z = 0.0
                self.publisher.publish(stop_cmd)
        
        self.prev_frame = cv_image

def main(args=None):
    rclpy.init(args=args)
    node = OpticalFlowTTC()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()