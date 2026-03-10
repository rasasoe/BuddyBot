#!/usr/bin/env python3
"""
Person Follower Node

This node generates velocity commands to follow a detected person.
It uses camera feedback to maintain distance and alignment.
Safety: Includes minimum distance checks to prevent collisions.
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from buddybot_msgs.msg import Command
from cv_bridge import CvBridge
import cv2
import numpy as np

class PersonFollower(Node):
    def __init__(self):
        super().__init__('person_follower')
        self.subscription = self.create_subscription(
            Image, 'camera/image_raw', self.image_callback, 10)
        self.publisher = self.create_publisher(Command, 'follow_command', 10)
        
        self.bridge = CvBridge()
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        
        self.target_distance = 1.5  # meters
        self.image_width = 640

    def image_callback(self, msg):
        cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
        
        boxes, weights = self.hog.detectMultiScale(cv_image, winStride=(8,8))
        
        if len(boxes) > 0:
            # Take the largest detection
            box = max(boxes, key=lambda b: b[2]*b[3])
            x, y, w, h = box
            
            # Center of person
            center_x = x + w/2
            center_y = y + h/2
            
            # Simple distance estimation based on box height
            distance = 2.0 / (h / self.image_width)  # Rough estimate
            
            # Generate command
            cmd = Command()
            if distance > self.target_distance + 0.2:
                cmd.linear_x = 0.2  # Move forward
            elif distance < self.target_distance - 0.2:
                cmd.linear_x = -0.1  # Move back
            
            # Turn towards center
            error = (center_x - self.image_width/2) / (self.image_width/2)
            cmd.angular_z = -error * 0.5
            
            self.publisher.publish(cmd)

def main(args=None):
    rclpy.init(args=args)
    node = PersonFollower()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()