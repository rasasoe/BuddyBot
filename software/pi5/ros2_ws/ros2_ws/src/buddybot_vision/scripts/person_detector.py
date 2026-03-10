#!/usr/bin/env python3
"""
Person Detector Node

This node detects persons in the camera feed using OpenCV.
It publishes bounding boxes and triggers person following mode.
Safety: Detection is used for following, not navigation, to avoid conflicts.
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge
import cv2

class PersonDetector(Node):
    def __init__(self):
        super().__init__('person_detector')
        self.subscription = self.create_subscription(
            Image, 'camera/image_raw', self.image_callback, 10)
        self.publisher = self.create_publisher(String, 'person_detected', 10)
        
        self.bridge = CvBridge()
        # Simple person detection using HOG
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def image_callback(self, msg):
        cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        
        # Detect persons
        boxes, weights = self.hog.detectMultiScale(cv_image, winStride=(8,8))
        
        if len(boxes) > 0:
            # Person detected
            detect_msg = String()
            detect_msg.data = 'follow'
            self.publisher.publish(detect_msg)
            self.get_logger().info('Person detected')

def main(args=None):
    rclpy.init(args=args)
    node = PersonDetector()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()