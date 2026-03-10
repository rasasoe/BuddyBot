#!/usr/bin/env python3
"""
Time-to-Collision (TTC) Node for BuddyBot

Estimates time-to-collision using optical flow to detect imminent collisions.
Uses Lucas-Kanade optical flow for efficient motion estimation on Raspberry Pi 5.

Algorithm:
- Tracks feature points between frames using optical flow
- Estimates time-to-collision based on expanding flow field
- Triggers emergency stop when TTC threshold is exceeded
- Optimized for real-time performance with configurable parameters

Architecture:
- Subscribes to camera image stream
- Publishes emergency stop events when collision imminent
- Configurable TTC thresholds and processing parameters
- Efficient feature tracking with quality filtering
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
import cv2
import cv_bridge
import numpy as np
from sensor_msgs.msg import Image
from std_msgs.msg import String
import time


class TTCNode(Node):
    """
    ROS 2 node for time-to-collision detection using optical flow.

    This node analyzes optical flow patterns to detect when the robot
    is approaching obstacles too quickly, providing an additional
    safety layer beyond person detection.
    """

    def __init__(self):
        super().__init__('ttc_node')

        # Declare parameters with sensible defaults
        self.declare_parameter('ttc_threshold', 2.0)      # seconds
        self.declare_parameter('min_features', 50)        # minimum features to track
        self.declare_parameter('max_features', 100)       # maximum features to track
        self.declare_parameter('feature_quality', 0.3)    # corner quality threshold
        self.declare_parameter('feature_min_distance', 7) # min distance between features
        self.declare_parameter('flow_win_size', 15)       # optical flow window size
        self.declare_parameter('flow_max_level', 2)       # optical flow pyramid levels
        self.declare_parameter('flow_criteria', [cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03])
        self.declare_parameter('motion_threshold', 0.5)   # minimum motion to consider
        self.declare_parameter('processing_interval', 3)  # process every N frames

        # Get parameters
        self.ttc_threshold = self.get_parameter('ttc_threshold').value
        self.min_features = self.get_parameter('min_features').value
        self.max_features = self.get_parameter('max_features').value
        self.feature_quality = self.get_parameter('feature_quality').value
        self.feature_min_distance = self.get_parameter('feature_min_distance').value
        self.flow_win_size = self.get_parameter('flow_win_size').value
        self.flow_max_level = self.get_parameter('flow_max_level').value
        self.flow_criteria = self.get_parameter('flow_criteria').value
        self.motion_threshold = self.get_parameter('motion_threshold').value
        self.processing_interval = self.get_parameter('processing_interval').value

        # Initialize OpenCV components
        self.bridge = cv_bridge.CvBridge()
        self.prev_frame = None
        self.prev_points = None

        # Frame counter for processing interval
        self.frame_count = 0

        # Lucas-Kanade parameters
        self.lk_params = dict(
            winSize=(self.flow_win_size, self.flow_win_size),
            maxLevel=self.flow_max_level,
            criteria=tuple(self.flow_criteria)
        )

        # Subscribers and publishers
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            depth=1
        )

        self.image_subscriber = self.create_subscription(
            Image, '/camera/image_raw', self.image_callback, qos_profile)

        self.ttc_publisher = self.create_publisher(
            String, '/vision/ttc_alert', qos_profile)

        self.get_logger().info("TTC node initialized")
        self._log_configuration()

    def _log_configuration(self):
        """Log current configuration."""
        self.get_logger().info("TTC Configuration:")
        self.get_logger().info(f"  TTC threshold: {self.ttc_threshold}s")
        self.get_logger().info(f"  Features: {self.min_features}-{self.max_features}")
        self.get_logger().info(f"  Feature quality: {self.feature_quality}")
        self.get_logger().info(f"  Processing interval: every {self.processing_interval} frames")
        self.get_logger().info(f"  Motion threshold: {self.motion_threshold}")

    def image_callback(self, msg: Image):
        """Process incoming camera images for TTC estimation."""
        try:
            # Convert ROS image to OpenCV
            current_frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

            # Convert to grayscale for optical flow
            current_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)

            # Increment frame counter
            self.frame_count += 1

            # Process at specified intervals
            if self.frame_count % self.processing_interval == 0:
                self._process_ttc(current_gray)

            # Update previous frame
            self.prev_frame = current_gray.copy()

        except cv_bridge.CvBridgeError as e:
            self.get_logger().error(f"CV Bridge error: {e}")
        except Exception as e:
            self.get_logger().error(f"Image processing error: {e}")

    def _process_ttc(self, current_gray):
        """Process optical flow and estimate time-to-collision."""
        if self.prev_frame is None:
            return

        try:
            # Find good features to track
            if self.prev_points is None:
                self.prev_points = cv2.goodFeaturesToTrack(
                    self.prev_frame,
                    maxCorners=self.max_features,
                    qualityLevel=self.feature_quality,
                    minDistance=self.feature_min_distance
                )

            if self.prev_points is None or len(self.prev_points) < self.min_features:
                # Not enough features to track
                return

            # Calculate optical flow
            current_points, status, error = cv2.calcOpticalFlowPyrLK(
                self.prev_frame, current_gray, self.prev_points, None, **self.lk_params)

            # Filter valid points
            if current_points is not None:
                good_prev = self.prev_points[status == 1]
                good_curr = current_points[status == 1]

                if len(good_prev) >= self.min_features:
                    # Estimate TTC from optical flow
                    ttc = self._estimate_ttc(good_prev, good_curr)

                    if ttc is not None and ttc < self.ttc_threshold:
                        self._publish_ttc_alert(ttc)
                        self.get_logger().warn(f"TTC alert: {ttc:.2f}s")

                    # Update tracking points
                    self.prev_points = cv2.goodFeaturesToTrack(
                        current_gray,
                        maxCorners=self.max_features,
                        qualityLevel=self.feature_quality,
                        minDistance=self.feature_min_distance
                    )
                else:
                    # Lost too many features, reset tracking
                    self.prev_points = None

        except Exception as e:
            self.get_logger().error(f"TTC processing error: {e}")
            self.prev_points = None

    def _estimate_ttc(self, prev_points, curr_points):
        """
        Estimate time-to-collision from optical flow vectors.

        Uses the principle that expanding flow indicates approaching motion.
        Returns TTC in seconds, or None if estimation unreliable.
        """
        if len(prev_points) != len(curr_points) or len(prev_points) < 4:
            return None

        try:
            # Calculate flow vectors
            flow_vectors = curr_points - prev_points

            # Calculate focus of expansion (FOE) - point where flow vectors diverge
            # For simplicity, use image center as approximation
            image_center = np.array([320, 240])  # Assuming 640x480

            # Calculate distances from center
            distances = np.linalg.norm(prev_points - image_center, axis=1)

            # Calculate flow magnitudes
            flow_magnitudes = np.linalg.norm(flow_vectors, axis=1)

            # Filter points with significant motion
            valid_indices = flow_magnitudes > self.motion_threshold
            if np.sum(valid_indices) < 4:
                return None

            valid_distances = distances[valid_indices]
            valid_flows = flow_magnitudes[valid_indices]

            # Estimate TTC using 1/rate of expansion
            # TTC ≈ distance / velocity
            # For expanding flow, use average distance and flow magnitude
            avg_distance = np.mean(valid_distances)
            avg_flow = np.mean(valid_flows)

            if avg_flow > 0:
                ttc = avg_distance / avg_flow
                return max(0.1, ttc)  # Clamp to reasonable range
            else:
                return None

        except Exception as e:
            self.get_logger().error(f"TTC estimation error: {e}")
            return None

    def _publish_ttc_alert(self, ttc):
        """Publish TTC alert message."""
        try:
            alert_msg = String()
            alert_msg.data = f"ttc:{ttc:.2f}"

            self.ttc_publisher.publish(alert_msg)

        except Exception as e:
            self.get_logger().error(f"Error publishing TTC alert: {e}")

    def destroy_node(self):
        """Clean shutdown."""
        self.get_logger().info("Shutting down TTC node")
        super().destroy_node()


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    try:
        node = TTCNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal error in TTC node: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()