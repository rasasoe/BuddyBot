#!/usr/bin/env python3
"""
Person Detector Node for BuddyBot

Performs lightweight person detection using OpenCV DNN with MobileNet-SSD.
Optimized for Raspberry Pi 5 with configurable detection intervals to reduce CPU load.

Architecture:
- Subscribes to camera image stream
- Runs detection every N frames to reduce processing load
- Uses OpenCV DNN with MobileNet-SSD for efficient person detection
- Publishes best person bounding box
- Optionally publishes debug image with detections
- Configurable confidence thresholds and model parameters
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
import cv2
import cv_bridge
import numpy as np
from sensor_msgs.msg import Image
from std_msgs.msg import Float32MultiArray
import os


class DetectorNode(Node):
    """
    ROS 2 node for person detection using lightweight neural network.

    This node provides efficient person detection optimized for embedded systems,
    with configurable detection intervals to balance accuracy and performance.
    """

    def __init__(self):
        super().__init__('detector_node')

        # Declare parameters
        self.declare_parameter('model_config', 'models/mobilenet_ssd_v2_coco.pbtxt')
        self.declare_parameter('model_weights', 'models/mobilenet_ssd_v2_coco.pb')
        self.declare_parameter('confidence_threshold', 0.5)
        self.declare_parameter('detection_interval', 5)  # Run detection every N frames
        self.declare_parameter('input_size', [300, 300])
        self.declare_parameter('mean_values', [127.5, 127.5, 127.5])
        self.declare_parameter('scale_factor', 0.007843)
        self.declare_parameter('publish_debug_image', False)
        self.declare_parameter('person_class_id', 15)  # COCO dataset person class

        # Get parameters
        self.model_config = self.get_parameter('model_config').value
        self.model_weights = self.get_parameter('model_weights').value
        self.confidence_threshold = self.get_parameter('confidence_threshold').value
        self.detection_interval = self.get_parameter('detection_interval').value
        self.input_size = self.get_parameter('input_size').value
        self.mean_values = self.get_parameter('mean_values').value
        self.scale_factor = self.get_parameter('scale_factor').value
        self.publish_debug = self.get_parameter('publish_debug_image').value
        self.person_class_id = self.get_parameter('person_class_id').value

        # Initialize OpenCV DNN
        self.net = None
        self.bridge = cv_bridge.CvBridge()

        # Frame counter for detection interval
        self.frame_count = 0

        # Subscribers and publishers
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            depth=1
        )

        self.image_subscriber = self.create_subscription(
            Image, '/camera/image_raw', self.image_callback, qos_profile)

        self.bbox_publisher = self.create_publisher(
            Float32MultiArray, '/vision/person_bbox', qos_profile)

        if self.publish_debug:
            self.debug_publisher = self.create_publisher(
                Image, '/vision/debug_image', qos_profile)

        # Initialize detector
        self._initialize_detector()

        self.get_logger().info("Person detector node initialized")
        self._log_configuration()

    def _log_configuration(self):
        """Log current configuration."""
        self.get_logger().info("Detector Configuration:")
        self.get_logger().info(f"  Model config: {self.model_config}")
        self.get_logger().info(f"  Model weights: {self.model_weights}")
        self.get_logger().info(f"  Confidence threshold: {self.confidence_threshold}")
        self.get_logger().info(f"  Detection interval: every {self.detection_interval} frames")
        self.get_logger().info(f"  Input size: {self.input_size}")
        self.get_logger().info(f"  Person class ID: {self.person_class_id}")
        self.get_logger().info(f"  Debug image: {'enabled' if self.publish_debug else 'disabled'}")

    def _initialize_detector(self):
        """Initialize the neural network detector."""
        try:
            # Check if model files exist
            if not os.path.exists(self.model_config):
                self.get_logger().warn(f"Model config file not found: {self.model_config}")
                return False

            if not os.path.exists(self.model_weights):
                self.get_logger().warn(f"Model weights file not found: {self.model_weights}")
                return False

            # Load the network
            self.net = cv2.dnn.readNetFromTensorflow(self.model_weights, self.model_config)

            # Optimize for CPU (Raspberry Pi 5)
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

            self.get_logger().info("Neural network loaded successfully")
            return True

        except Exception as e:
            self.get_logger().error(f"Failed to initialize detector: {e}")
            return False

    def image_callback(self, msg: Image):
        """Process incoming camera images."""
        try:
            # Convert ROS image to OpenCV
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')

            # Increment frame counter
            self.frame_count += 1

            # Run detection at specified intervals
            if self.frame_count % self.detection_interval == 0:
                self._run_detection(cv_image)

        except cv_bridge.CvBridgeError as e:
            self.get_logger().error(f"CV Bridge error: {e}")
        except Exception as e:
            self.get_logger().error(f"Image processing error: {e}")

    def _run_detection(self, image):
        """Run person detection on the image."""
        if self.net is None:
            self.get_logger().warn("Detector not initialized")
            return

        try:
            height, width = image.shape[:2]

            # Prepare blob for network
            blob = cv2.dnn.blobFromImage(
                image,
                self.scale_factor,
                tuple(self.input_size),
                tuple(self.mean_values),
                swapRB=True,
                crop=False
            )

            # Run forward pass
            self.net.setInput(blob)
            detections = self.net.forward()

            # Process detections
            best_person = self._find_best_person(detections, width, height)

            if best_person:
                # Publish bounding box
                self._publish_bbox(best_person)

                # Publish debug image if enabled
                if self.publish_debug:
                    debug_image = self._draw_detection(image.copy(), best_person)
                    self._publish_debug_image(debug_image)

                self.get_logger().debug(f"Detected person: {best_person}")
            else:
                self.get_logger().debug("No person detected")

        except Exception as e:
            self.get_logger().error(f"Detection error: {e}")

    def _find_best_person(self, detections, image_width, image_height):
        """
        Find the best person detection based on confidence and size.

        Returns:
            dict with 'x', 'y', 'width', 'height', 'confidence' or None
        """
        best_detection = None
        best_score = 0

        # Detection format: [batch_id, class_id, confidence, x1, y1, x2, y2]
        for detection in detections[0, 0]:
            class_id = int(detection[1])
            confidence = float(detection[2])

            # Only process person detections above threshold
            if class_id == self.person_class_id and confidence > self.confidence_threshold:
                # Extract bounding box
                x1 = int(detection[3] * image_width)
                y1 = int(detection[4] * image_height)
                x2 = int(detection[5] * image_width)
                y2 = int(detection[6] * image_height)

                width = x2 - x1
                height = y2 - y1

                # Calculate score (confidence * size)
                size_score = width * height
                total_score = confidence * size_score

                if total_score > best_score:
                    best_score = total_score
                    best_detection = {
                        'x': x1,
                        'y': y1,
                        'width': width,
                        'height': height,
                        'confidence': confidence
                    }

        return best_detection

    def _publish_bbox(self, detection):
        """Publish person bounding box."""
        try:
            bbox_msg = Float32MultiArray()
            bbox_msg.data = [
                float(detection['x']),
                float(detection['y']),
                float(detection['width']),
                float(detection['height']),
                detection['confidence']
            ]

            self.bbox_publisher.publish(bbox_msg)

        except Exception as e:
            self.get_logger().error(f"Error publishing bbox: {e}")

    def _publish_debug_image(self, image):
        """Publish debug image with detection overlay."""
        try:
            ros_image = self.bridge.cv2_to_imgmsg(image, encoding='bgr8')
            ros_image.header.stamp = self.get_clock().now().to_msg()
            ros_image.header.frame_id = 'camera_link'

            self.debug_publisher.publish(ros_image)

        except Exception as e:
            self.get_logger().error(f"Error publishing debug image: {e}")

    def _draw_detection(self, image, detection):
        """Draw bounding box on image for debugging."""
        x, y, w, h = detection['x'], detection['y'], detection['width'], detection['height']
        conf = detection['confidence']

        # Draw rectangle
        cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # Draw label
        label = f"Person: {conf:.2f}"
        cv2.putText(image, label, (x, y - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        return image

    def destroy_node(self):
        """Clean shutdown."""
        self.get_logger().info("Shutting down detector node")
        super().destroy_node()


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    try:
        node = DetectorNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal error in detector node: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()