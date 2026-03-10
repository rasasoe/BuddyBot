#!/usr/bin/env python3
"""
Follow Controller Node for BuddyBot

Computes velocity commands to follow detected person based on bounding box.
Uses simple proportional control with configurable gains.

Control Logic:
- Center offset controls angular velocity (yaw)
- Box height approximates distance (forward/backward velocity)
- Maintains safe following distance
- Smooth velocity commands to avoid jerky motion

Architecture:
- Subscribes to person bounding box
- Publishes velocity commands for following
- Configurable control gains and thresholds
- Safety limits on velocity outputs
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from geometry_msgs.msg import Twist
from std_msgs.msg import Float32MultiArray
import math


class FollowControllerNode(Node):
    """
    ROS 2 node for person following control.

    This node implements a simple proportional controller that generates
    velocity commands to follow a detected person based on their bounding box.
    """

    def __init__(self):
        super().__init__('follow_controller_node')

        # Declare parameters with practical defaults
        self.declare_parameter('image_width', 640)
        self.declare_parameter('image_height', 480)
        self.declare_parameter('center_x_gain', 0.002)  # Angular velocity gain for center offset
        self.declare_parameter('height_gain', 0.0005)   # Linear velocity gain for box height
        self.declare_parameter('target_height_ratio', 0.6)  # Target box height as fraction of image
        self.declare_parameter('max_linear_velocity', 0.3)   # m/s
        self.declare_parameter('max_angular_velocity', 0.5)  # rad/s
        self.declare_parameter('deadzone_center', 20)        # pixels, ignore small center offsets
        self.declare_parameter('deadzone_height', 10)        # pixels, ignore small height changes

        # Get parameters
        self.image_width = self.get_parameter('image_width').value
        self.image_height = self.get_parameter('image_height').value
        self.center_x_gain = self.get_parameter('center_x_gain').value
        self.height_gain = self.get_parameter('height_gain').value
        self.target_height_ratio = self.get_parameter('target_height_ratio').value
        self.max_linear_vel = self.get_parameter('max_linear_velocity').value
        self.max_angular_vel = self.get_parameter('max_angular_velocity').value
        self.deadzone_center = self.get_parameter('deadzone_center').value
        self.deadzone_height = self.get_parameter('deadzone_height').value

        # Calculate target height in pixels
        self.target_height = self.image_height * self.target_height_ratio

        # Publisher for velocity commands
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            depth=10
        )

        self.cmd_publisher = self.create_publisher(
            Twist, '/cmd_vel_follow', qos_profile)

        # Subscriber for person bounding box
        self.bbox_subscriber = self.create_subscription(
            Float32MultiArray, '/vision/person_bbox', self.bbox_callback, qos_profile)

        # State
        self.last_bbox_time = self.get_clock().now()
        self.following_active = False

        self.get_logger().info("Follow controller node initialized")
        self._log_configuration()

    def _log_configuration(self):
        """Log current configuration."""
        self.get_logger().info("Follow Controller Configuration:")
        self.get_logger().info(f"  Image size: {self.image_width}x{self.image_height}")
        self.get_logger().info(f"  Center X gain: {self.center_x_gain}")
        self.get_logger().info(f"  Height gain: {self.height_gain}")
        self.get_logger().info(f"  Target height ratio: {self.target_height_ratio} ({self.target_height:.0f}px)")
        self.get_logger().info(f"  Max velocities: linear={self.max_linear_vel}, angular={self.max_angular_vel}")
        self.get_logger().info(f"  Deadzones: center={self.deadzone_center}px, height={self.deadzone_height}px")

    def bbox_callback(self, msg: Float32MultiArray):
        """Process person bounding box and compute following velocities."""
        try:
            if len(msg.data) < 5:
                self.get_logger().warn("Invalid bbox message format")
                return

            # Extract bounding box data
            x, y, width, height, confidence = msg.data[:5]

            # Update state
            self.last_bbox_time = self.get_clock().now()
            self.following_active = True

            # Compute control commands
            twist = self._compute_follow_velocity(x, y, width, height)

            # Publish velocity command
            self.cmd_publisher.publish(twist)

            self.get_logger().debug(f"Following person: x={x:.0f}, height={height:.0f}, vx={twist.linear.x:.3f}, wz={twist.angular.z:.3f}")

        except Exception as e:
            self.get_logger().error(f"Error processing bbox: {e}")

    def _compute_follow_velocity(self, bbox_x, bbox_y, bbox_width, bbox_height):
        """
        Compute velocity commands based on person bounding box.

        Control Strategy:
        - Angular velocity proportional to center offset (left/right turning)
        - Linear velocity based on box height (distance approximation)
        - Deadzones prevent jittery motion
        - Velocity limits for safety
        """
        twist = Twist()

        # Calculate center offset (negative = person left of center, positive = right)
        person_center_x = bbox_x + bbox_width / 2
        image_center_x = self.image_width / 2
        center_offset = person_center_x - image_center_x

        # Apply deadzone for center control
        if abs(center_offset) > self.deadzone_center:
            # Angular velocity proportional to center offset
            angular_vel = -center_offset * self.center_x_gain

            # Limit angular velocity
            angular_vel = max(-self.max_angular_vel, min(self.max_angular_vel, angular_vel))
            twist.angular.z = angular_vel

        # Calculate height error (negative = too far, positive = too close)
        height_error = bbox_height - self.target_height

        # Apply deadzone for height control
        if abs(height_error) > self.deadzone_height:
            # Linear velocity proportional to height error
            # Negative height_error means person is far, so move forward (positive vx)
            linear_vel = -height_error * self.height_gain

            # Limit linear velocity
            linear_vel = max(-self.max_linear_vel, min(self.max_linear_vel, linear_vel))
            twist.linear.x = linear_vel

        return twist

    def destroy_node(self):
        """Clean shutdown."""
        self.get_logger().info("Shutting down follow controller node")

        # Publish zero velocity on shutdown for safety
        zero_twist = Twist()
        self.cmd_publisher.publish(zero_twist)

        super().destroy_node()


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    try:
        node = FollowControllerNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal error in follow controller node: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()