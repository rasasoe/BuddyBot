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
from std_msgs.msg import Bool
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
        self.declare_parameter('image_width', 320)
        self.declare_parameter('image_height', 240)
        self.declare_parameter('center_x_gain', 0.008)  # Angular velocity gain for center offset
        self.declare_parameter('height_gain', 0.012)    # Linear velocity gain for box height
        self.declare_parameter('target_height_ratio', 0.55)  # Target box height as fraction of image
        self.declare_parameter('max_linear_velocity', 0.75)  # normalized 0-1 (pico maps directly to PWM)
        self.declare_parameter('max_angular_velocity', 0.80)  # normalized 0-1
        self.declare_parameter('deadzone_center', 15)        # pixels, ignore small center offsets
        self.declare_parameter('deadzone_height', 5)         # pixels, ignore small height changes
        self.declare_parameter('follow_enabled_topic', '/follow/enabled')
        self.declare_parameter('bbox_timeout_sec', 0.8)
        self.declare_parameter('min_detection_confidence', 0.15)

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
        self.follow_enabled_topic = self.get_parameter('follow_enabled_topic').value
        self.bbox_timeout_sec = float(self.get_parameter('bbox_timeout_sec').value)
        self.min_detection_confidence = float(self.get_parameter('min_detection_confidence').value)

        # Calculate target height in pixels
        self.target_height = self.image_height * self.target_height_ratio

        # Publisher for velocity commands
        command_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            depth=10
        )
        bbox_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            depth=1
        )

        self.cmd_publisher = self.create_publisher(
            Twist, '/cmd_vel_follow', command_qos)

        # Subscriber for person bounding box
        self.bbox_subscriber = self.create_subscription(
            Float32MultiArray, '/vision/person_bbox', self.bbox_callback, bbox_qos)
        self.follow_enabled_subscriber = self.create_subscription(
            Bool, self.follow_enabled_topic, self.follow_enabled_callback, command_qos)
        self.watchdog_timer = self.create_timer(0.1, self.watchdog_callback)

        # State
        self.last_bbox_time = self.get_clock().now()
        self.following_active = False
        self.follow_enabled = False
        self.last_command_was_nonzero = False

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
        self.get_logger().info(f"  Follow enable topic: {self.follow_enabled_topic}")
        self.get_logger().info(f"  BBox timeout: {self.bbox_timeout_sec:.2f}s")
        self.get_logger().info(f"  Min detection confidence: {self.min_detection_confidence:.2f}")

    def follow_enabled_callback(self, msg: Bool):
        """Enable or disable following based on external control."""
        new_state = bool(msg.data)
        if new_state == self.follow_enabled:
            return

        self.follow_enabled = new_state
        if not new_state:
            self.following_active = False
            self._publish_zero_velocity("follow disabled")

        state = "enabled" if self.follow_enabled else "disabled"
        self.get_logger().info(f"Follow controller {state}")

    def bbox_callback(self, msg: Float32MultiArray):
        """Process person bounding box and compute following velocities."""
        try:
            if not self.follow_enabled:
                return

            if len(msg.data) < 5:
                self.get_logger().warn("Invalid bbox message format")
                return

            # Extract bounding box data
            x, y, width, height, confidence = msg.data[:5]
            if float(confidence) < self.min_detection_confidence:
                self.get_logger().debug(f"Ignoring low-confidence detection: {confidence:.2f}")
                return

            # Update state
            self.last_bbox_time = self.get_clock().now()
            self.following_active = True

            # Compute control commands
            twist = self._compute_follow_velocity(x, y, width, height)

            # Publish velocity command
            self.cmd_publisher.publish(twist)
            self.last_command_was_nonzero = not self._is_zero_twist(twist)

            self.get_logger().debug(f"Following person: x={x:.0f}, height={height:.0f}, vx={twist.linear.x:.3f}, wz={twist.angular.z:.3f}")

        except Exception as e:
            self.get_logger().error(f"Error processing bbox: {e}")

    def watchdog_callback(self):
        """Stop the robot if following is disabled or detections go stale."""
        if not self.follow_enabled:
            if self.last_command_was_nonzero:
                self._publish_zero_velocity("follow disabled watchdog")
            return

        if not self.following_active:
            return

        elapsed = (self.get_clock().now() - self.last_bbox_time).nanoseconds / 1e9
        if elapsed > self.bbox_timeout_sec:
            self.following_active = False
            self._publish_zero_velocity("bbox timeout")

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

    def _is_zero_twist(self, twist: Twist) -> bool:
        return (
            abs(twist.linear.x) < 1e-4
            and abs(twist.linear.y) < 1e-4
            and abs(twist.angular.z) < 1e-4
        )

    def _publish_zero_velocity(self, reason: str):
        zero_twist = Twist()
        self.cmd_publisher.publish(zero_twist)
        self.last_command_was_nonzero = False
        self.get_logger().debug(f"Published zero follow velocity: {reason}")

    def destroy_node(self):
        """Clean shutdown."""
        self.get_logger().info("Shutting down follow controller node")

        # Publish zero velocity on shutdown for safety
        self._publish_zero_velocity("shutdown")

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
