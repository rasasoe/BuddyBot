#!/usr/bin/env python3
"""
Person detector node for BuddyBot.

Primary backend:
- OpenCV DNN with MobileNet-SSD when model files are available

Offline fallback:
- OpenCV HOG people detector when the DNN assets are missing

The node publishes:
- /vision/person_bbox
- /vision/detector_status
- optionally /vision/debug_image
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import cv_bridge
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import Image
from std_msgs.msg import Float32MultiArray, String

try:
    from ament_index_python.packages import get_package_share_directory
except Exception:
    get_package_share_directory = None


PACKAGE_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = PACKAGE_DIR.parent


def _first_existing_path(candidates: List[Path]) -> Path:
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate.resolve()
        except OSError:
            continue
    return candidates[0].resolve()


def _as_int_pair(values: List[int], default: Tuple[int, int]) -> Tuple[int, int]:
    if not values or len(values) < 2:
        return default
    return (int(values[0]), int(values[1]))


class DetectorNode(Node):
    """ROS 2 node for offline-friendly person detection."""

    def __init__(self):
        super().__init__("detector_node")

        self.declare_parameter("model_config", "models/mobilenet_ssd_v2_coco.pbtxt")
        self.declare_parameter("model_weights", "models/mobilenet_ssd_v2_coco.pb")
        self.declare_parameter("confidence_threshold", 0.5)
        self.declare_parameter("detection_interval", 5)
        self.declare_parameter("input_size", [300, 300])
        self.declare_parameter("mean_values", [127.5, 127.5, 127.5])
        self.declare_parameter("scale_factor", 0.007843)
        self.declare_parameter("publish_debug_image", False)
        self.declare_parameter("person_class_id", 15)
        self.declare_parameter("allow_hog_fallback", True)
        self.declare_parameter("hog_confidence_threshold", 0.12)
        self.declare_parameter("hog_resize_width", 480)
        self.declare_parameter("hog_win_stride", [8, 8])
        self.declare_parameter("hog_padding", [8, 8])
        self.declare_parameter("hog_scale", 1.03)
        self.declare_parameter("status_topic", "/vision/detector_status")

        self.model_config = str(self.get_parameter("model_config").value)
        self.model_weights = str(self.get_parameter("model_weights").value)
        self.confidence_threshold = float(self.get_parameter("confidence_threshold").value)
        self.detection_interval = max(1, int(self.get_parameter("detection_interval").value))
        self.input_size = _as_int_pair(list(self.get_parameter("input_size").value), (300, 300))
        self.mean_values = tuple(float(v) for v in self.get_parameter("mean_values").value)
        self.scale_factor = float(self.get_parameter("scale_factor").value)
        self.publish_debug = bool(self.get_parameter("publish_debug_image").value)
        self.person_class_id = int(self.get_parameter("person_class_id").value)
        self.allow_hog_fallback = bool(self.get_parameter("allow_hog_fallback").value)
        self.hog_confidence_threshold = float(self.get_parameter("hog_confidence_threshold").value)
        self.hog_resize_width = int(self.get_parameter("hog_resize_width").value)
        self.hog_win_stride = _as_int_pair(list(self.get_parameter("hog_win_stride").value), (8, 8))
        self.hog_padding = _as_int_pair(list(self.get_parameter("hog_padding").value), (8, 8))
        self.hog_scale = float(self.get_parameter("hog_scale").value)
        self.status_topic = str(self.get_parameter("status_topic").value)

        self.model_config_path = self._resolve_resource_path(self.model_config)
        self.model_weights_path = self._resolve_resource_path(self.model_weights)

        self.bridge = cv_bridge.CvBridge()
        self.net = None
        self.hog = None
        self.frame_count = 0
        self.detector_backend = "unavailable"
        self.detector_ready = False
        self.detector_reason = "initializing"
        self.detector_details = "initializing"
        self._last_status_payload = ""
        self._last_not_ready_log = self.get_clock().now()

        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            depth=1,
        )

        self.image_subscriber = self.create_subscription(
            Image, "/camera/image_raw", self.image_callback, qos_profile
        )
        self.bbox_publisher = self.create_publisher(
            Float32MultiArray, "/vision/person_bbox", qos_profile
        )
        self.status_publisher = self.create_publisher(String, self.status_topic, 10)

        if self.publish_debug:
            self.debug_publisher = self.create_publisher(Image, "/vision/debug_image", qos_profile)

        self._initialize_detector()
        self.create_timer(1.0, self._publish_status)

        self.get_logger().info("Person detector node initialized")
        self._log_configuration()
        self._publish_status(force=True)

    def _candidate_paths(self, raw_path: str) -> List[Path]:
        candidate = Path(raw_path).expanduser()
        candidates: List[Path] = []

        if candidate.is_absolute():
            candidates.append(candidate)
        else:
            candidates.extend(
                [
                    Path.cwd() / candidate,
                    PACKAGE_ROOT / candidate,
                    PACKAGE_ROOT / "models" / candidate.name,
                    PACKAGE_DIR / candidate,
                ]
            )

        if get_package_share_directory is not None:
            try:
                share_dir = Path(get_package_share_directory("buddybot_vision"))
                candidates.extend(
                    [
                        share_dir / candidate,
                        share_dir / "models" / candidate.name,
                    ]
                )
            except Exception:
                pass

        candidates.append(candidate)
        return candidates

    def _resolve_resource_path(self, raw_path: str) -> Path:
        return _first_existing_path(self._candidate_paths(raw_path))

    def _set_detector_status(self, backend: str, ready: bool, reason: str, details: str) -> None:
        state_changed = (
            backend != self.detector_backend
            or bool(ready) != self.detector_ready
            or reason != self.detector_reason
            or details != self.detector_details
        )

        self.detector_backend = backend
        self.detector_ready = bool(ready)
        self.detector_reason = reason
        self.detector_details = details

        if state_changed:
            level = self.get_logger().info if self.detector_ready else self.get_logger().warn
            level(
                f"Detector status changed: backend={self.detector_backend}, "
                f"ready={self.detector_ready}, reason={self.detector_reason}"
            )

    def _status_payload(self) -> str:
        return json.dumps(
            {
                "backend": self.detector_backend,
                "ready": self.detector_ready,
                "reason": self.detector_reason,
                "details": self.detector_details,
                "model_config": str(self.model_config_path),
                "model_weights": str(self.model_weights_path),
            },
            ensure_ascii=False,
        )

    def _publish_status(self, force: bool = False) -> None:
        payload = self._status_payload()
        msg = String()
        msg.data = payload
        self.status_publisher.publish(msg)
        self._last_status_payload = payload

    def _log_configuration(self) -> None:
        self.get_logger().info("Detector configuration:")
        self.get_logger().info(f"  Model config: {self.model_config_path}")
        self.get_logger().info(f"  Model weights: {self.model_weights_path}")
        self.get_logger().info(f"  Confidence threshold: {self.confidence_threshold}")
        self.get_logger().info(f"  Detection interval: every {self.detection_interval} frames")
        self.get_logger().info(f"  Input size: {self.input_size}")
        self.get_logger().info(f"  HOG fallback: {'enabled' if self.allow_hog_fallback else 'disabled'}")
        self.get_logger().info(f"  Active backend: {self.detector_backend}")
        self.get_logger().info(f"  Debug image: {'enabled' if self.publish_debug else 'disabled'}")

    def _initialize_hog(self, reason: str) -> bool:
        if not self.allow_hog_fallback:
            self._set_detector_status("unavailable", False, reason, "HOG fallback disabled")
            return False

        try:
            self.hog = cv2.HOGDescriptor()
            self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            self._set_detector_status("hog", True, reason, "Using OpenCV HOG fallback")
            return True
        except Exception as exc:
            self.hog = None
            self._set_detector_status("unavailable", False, "hog_init_failed", repr(exc))
            return False

    def _initialize_detector(self) -> bool:
        try:
            config_exists = self.model_config_path.exists()
            weights_exists = self.model_weights_path.exists()
            if config_exists and weights_exists:
                self.net = cv2.dnn.readNetFromTensorflow(
                    str(self.model_weights_path),
                    str(self.model_config_path),
                )
                self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                self._set_detector_status("dnn", True, "model_loaded", "MobileNet-SSD loaded")
                return True

            missing: List[str] = []
            if not config_exists:
                missing.append("config")
            if not weights_exists:
                missing.append("weights")
            return self._initialize_hog(f"model_missing:{'+'.join(missing)}")
        except Exception as exc:
            self.net = None
            return self._initialize_hog(f"dnn_init_failed:{type(exc).__name__}")

    def image_callback(self, msg: Image) -> None:
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            self.frame_count += 1
            if self.frame_count % self.detection_interval == 0:
                self._run_detection(cv_image)
        except cv_bridge.CvBridgeError as exc:
            self.get_logger().error(f"CV bridge error: {exc}")
        except Exception as exc:
            self.get_logger().error(f"Image processing error: {exc}")

    def _log_unavailable_detector(self) -> None:
        now = self.get_clock().now()
        elapsed = (now - self._last_not_ready_log).nanoseconds / 1e9
        if elapsed >= 5.0:
            self._last_not_ready_log = now
            self.get_logger().warn(
                f"Detector unavailable: backend={self.detector_backend}, reason={self.detector_reason}"
            )

    def _run_detection(self, image) -> None:
        if not self.detector_ready:
            self._log_unavailable_detector()
            return

        try:
            if self.detector_backend == "dnn":
                best_person = self._run_dnn_detection(image)
            elif self.detector_backend == "hog":
                best_person = self._run_hog_detection(image)
            else:
                best_person = None

            if best_person is None:
                return

            self._publish_bbox(best_person)
            if self.publish_debug:
                debug_image = self._draw_detection(image.copy(), best_person)
                self._publish_debug_image(debug_image)
        except Exception as exc:
            self.get_logger().error(f"Detection error: {exc}")

    def _run_dnn_detection(self, image) -> Optional[Dict[str, float]]:
        if self.net is None:
            return None

        height, width = image.shape[:2]
        blob = cv2.dnn.blobFromImage(
            image,
            self.scale_factor,
            self.input_size,
            self.mean_values,
            swapRB=True,
            crop=False,
        )
        self.net.setInput(blob)
        detections = self.net.forward()
        return self._find_best_person_dnn(detections, width, height)

    def _run_hog_detection(self, image) -> Optional[Dict[str, float]]:
        if self.hog is None:
            return None

        image_height, image_width = image.shape[:2]
        scale_ratio = 1.0
        working = image

        if self.hog_resize_width > 0 and image_width > self.hog_resize_width:
            scale_ratio = image_width / float(self.hog_resize_width)
            resized_height = max(1, int(round(image_height / scale_ratio)))
            working = cv2.resize(image, (self.hog_resize_width, resized_height))

        rects, weights = self.hog.detectMultiScale(
            working,
            winStride=self.hog_win_stride,
            padding=self.hog_padding,
            scale=self.hog_scale,
        )

        best_detection = None
        best_score = 0.0

        for (x, y, width, height), weight in zip(rects, weights):
            confidence = float(weight[0] if hasattr(weight, "__len__") else weight)
            if confidence < self.hog_confidence_threshold:
                continue

            mapped_x = int(round(x * scale_ratio))
            mapped_y = int(round(y * scale_ratio))
            mapped_w = int(round(width * scale_ratio))
            mapped_h = int(round(height * scale_ratio))

            size_score = mapped_w * mapped_h
            total_score = confidence * size_score
            if total_score > best_score:
                best_score = total_score
                best_detection = {
                    "x": mapped_x,
                    "y": mapped_y,
                    "width": mapped_w,
                    "height": mapped_h,
                    "confidence": confidence,
                }

        return best_detection

    def _find_best_person_dnn(
        self,
        detections,
        image_width: int,
        image_height: int,
    ) -> Optional[Dict[str, float]]:
        best_detection = None
        best_score = 0.0

        for detection in detections[0, 0]:
            class_id = int(detection[1])
            confidence = float(detection[2])
            if class_id != self.person_class_id or confidence < self.confidence_threshold:
                continue

            x1 = max(0, int(detection[3] * image_width))
            y1 = max(0, int(detection[4] * image_height))
            x2 = min(image_width, int(detection[5] * image_width))
            y2 = min(image_height, int(detection[6] * image_height))
            width = max(0, x2 - x1)
            height = max(0, y2 - y1)

            size_score = width * height
            total_score = confidence * size_score
            if total_score > best_score:
                best_score = total_score
                best_detection = {
                    "x": x1,
                    "y": y1,
                    "width": width,
                    "height": height,
                    "confidence": confidence,
                }

        return best_detection

    def _publish_bbox(self, detection: Dict[str, float]) -> None:
        try:
            bbox_msg = Float32MultiArray()
            bbox_msg.data = [
                float(detection["x"]),
                float(detection["y"]),
                float(detection["width"]),
                float(detection["height"]),
                float(detection["confidence"]),
            ]
            self.bbox_publisher.publish(bbox_msg)
        except Exception as exc:
            self.get_logger().error(f"Error publishing bbox: {exc}")

    def _publish_debug_image(self, image) -> None:
        try:
            ros_image = self.bridge.cv2_to_imgmsg(image, encoding="bgr8")
            ros_image.header.stamp = self.get_clock().now().to_msg()
            ros_image.header.frame_id = "camera_link"
            self.debug_publisher.publish(ros_image)
        except Exception as exc:
            self.get_logger().error(f"Error publishing debug image: {exc}")

    def _draw_detection(self, image, detection: Dict[str, float]):
        x = int(detection["x"])
        y = int(detection["y"])
        width = int(detection["width"])
        height = int(detection["height"])
        confidence = float(detection["confidence"])

        cv2.rectangle(image, (x, y), (x + width, y + height), (0, 255, 0), 2)
        label = f"{self.detector_backend.upper()} person {confidence:.2f}"
        cv2.putText(
            image,
            label,
            (x, max(20, y - 10)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            2,
        )
        return image

    def destroy_node(self) -> None:
        self.get_logger().info("Shutting down detector node")
        self._set_detector_status("unavailable", False, "shutdown", "node destroyed")
        self._publish_status(force=True)
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)

    try:
        node = DetectorNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"Fatal error in detector node: {exc}")
    finally:
        rclpy.shutdown()


if __name__ == "__main__":
    main()
