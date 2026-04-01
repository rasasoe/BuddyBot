#!/usr/bin/env python3
"""
Camera Node for BuddyBot

Captures video frames from camera device and publishes them as ROS 2 image messages.
Optimized for Raspberry Pi 5 with efficient capture and minimal processing.

Architecture:
- Uses OpenCV VideoCapture for camera access
- Publishes sensor_msgs/Image messages
- Configurable frame rate and resolution
- Graceful error handling for camera disconnection
- Low-latency operation for real-time vision processing
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy
import cv2
import cv_bridge
import glob
from sensor_msgs.msg import Image
import time


class CameraNode(Node):
    """
    ROS 2 node for camera capture and image publishing.

    This node provides a clean interface between camera hardware and
    vision processing nodes, handling camera initialization, frame capture,
    and ROS message publishing with appropriate QoS settings.
    """

    def __init__(self):
        super().__init__('camera_node')

        # Declare parameters with sensible defaults for Raspberry Pi camera
        self.declare_parameter('device', 'auto')
        self.declare_parameter('width', 640)
        self.declare_parameter('height', 480)
        self.declare_parameter('fps', 30.0)
        self.declare_parameter('frame_id', 'camera_link')
        self.declare_parameter('publish_rate', 30.0)  # Hz

        # Get parameters
        self.device = self.get_parameter('device').value
        self.width = self.get_parameter('width').value
        self.height = self.get_parameter('height').value
        self.fps = self.get_parameter('fps').value
        self.frame_id = self.get_parameter('frame_id').value
        self.publish_rate = self.get_parameter('publish_rate').value

        # Initialize camera
        self.cap = None
        self.bridge = cv_bridge.CvBridge()

        # Publisher with appropriate QoS for video streaming
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1
        )

        self.image_publisher = self.create_publisher(
            Image, '/camera/image_raw', qos_profile)

        # Timer for frame capture and publishing
        self.timer_period = 1.0 / self.publish_rate
        self.timer = self.create_timer(self.timer_period, self.timer_callback)

        # Initialize camera
        self._initialize_camera()

        self.get_logger().info("Camera node initialized")
        self._log_configuration()

    def _log_configuration(self):
        """Log current configuration for debugging."""
        self.get_logger().info("Camera Configuration:")
        self.get_logger().info(f"  Device: {self.device}")
        self.get_logger().info(f"  Resolution: {self.width}x{self.height}")
        self.get_logger().info(f"  FPS: {self.fps}")
        self.get_logger().info(f"  Publish rate: {self.publish_rate} Hz")
        self.get_logger().info(f"  Frame ID: {self.frame_id}")

    def _initialize_camera(self):
        """Initialize camera capture with error handling."""
        try:
            selected_device = self._detect_camera_device()
            if selected_device is None:
                self.get_logger().error("Failed to find a working camera device")
                return False

            self.device = selected_device
            self.cap = cv2.VideoCapture(self.device)

            if not self.cap.isOpened():
                self.get_logger().error(f"Failed to open camera device: {self.device}")
                return False

            # Set camera properties
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)

            # Verify settings
            actual_width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            actual_fps = self.cap.get(cv2.CAP_PROP_FPS)

            self.get_logger().info("Camera initialized successfully")
            self.get_logger().info(f"  Actual resolution: {actual_width}x{actual_height}")
            self.get_logger().info(f"  Actual FPS: {actual_fps}")

            return True

        except Exception as e:
            self.get_logger().error(f"Camera initialization error: {e}")
            return False

    def _detect_camera_device(self):
        requested = str(self.device).strip()
        candidates = []
        if requested and requested.lower() != 'auto':
            candidates.append(requested)
        candidates.extend(sorted(glob.glob('/dev/video*')))

        tried = set()
        for candidate in candidates:
            if candidate in tried:
                continue
            tried.add(candidate)
            cap = None
            try:
                cap = cv2.VideoCapture(candidate)
                if not cap.isOpened():
                    continue
                ok, _ = cap.read()
                if ok:
                    self.get_logger().info(f"Selected camera device: {candidate}")
                    return candidate
            except Exception:
                continue
            finally:
                if cap is not None:
                    cap.release()
        return None

    def timer_callback(self):
        """Timer callback for frame capture and publishing."""
        if not self.cap or not self.cap.isOpened():
            self.get_logger().warn("Camera not available, attempting to reinitialize")
            self._initialize_camera()
            return

        try:
            # Capture frame
            ret, frame = self.cap.read()

            if not ret or frame is None:
                self.get_logger().warn("Failed to capture frame")
                return

            # Convert to ROS Image message
            try:
                ros_image = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
                ros_image.header.frame_id = self.frame_id
                ros_image.header.stamp = self.get_clock().now().to_msg()

                # Publish image
                self.image_publisher.publish(ros_image)

                self.get_logger().debug("Published camera frame")

            except cv_bridge.CvBridgeError as e:
                self.get_logger().error(f"CV Bridge error: {e}")

        except Exception as e:
            self.get_logger().error(f"Frame capture error: {e}")

    def destroy_node(self):
        """Clean shutdown."""
        self.get_logger().info("Shutting down camera node")

        if self.cap and self.cap.isOpened():
            self.cap.release()

        super().destroy_node()


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    try:
        node = CameraNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal error in camera node: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()
