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

import json
import math

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, Float32MultiArray, String


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
        self.declare_parameter('center_x_gain', 0.0008)  # Angular velocity gain for center offset
        self.declare_parameter('height_gain', 0.010)    # Linear velocity gain for box height
        self.declare_parameter('target_height_ratio', 0.90)  # Target box height as fraction of image
        self.declare_parameter('max_linear_velocity', 0.42)  # normalized 0-1 (pico maps directly to PWM)
        self.declare_parameter('max_angular_velocity', 0.07)  # normalized 0-1
        self.declare_parameter('min_linear_velocity', 0.34)  # manual-like floor for gearbox stiction
        self.declare_parameter('deadzone_center', 50)        # pixels, ignore small center offsets
        self.declare_parameter('deadzone_height', 16)        # pixels, ignore small height changes
        self.declare_parameter('follow_enabled_topic', '/follow/enabled')
        self.declare_parameter('bbox_timeout_sec', 2.5)
        self.declare_parameter('max_source_age_sec', 0.0)
        self.declare_parameter('min_detection_confidence', 0.15)
        self.declare_parameter('command_rate_hz', 10.0)
        self.declare_parameter('linear_accel_limit', 0.55)   # normalized units per second
        self.declare_parameter('angular_accel_limit', 0.08)  # normalized units per second
        self.declare_parameter('bbox_smoothing_alpha', 0.45)
        self.declare_parameter('bbox_filter_reset_sec', 0.9)
        self.declare_parameter('allow_reverse', False)
        self.declare_parameter('visible_forward_velocity', 0.34)
        self.declare_parameter('visible_forward_center_deadzone', 120)
        self.declare_parameter('visible_forward_max_height_ratio', 0.94)
        self.declare_parameter('use_lidar_distance', False)
        self.declare_parameter('scan_topic', '/scan')
        self.declare_parameter('scan_forward_center_deg', 180.0)
        self.declare_parameter('camera_horizontal_fov_deg', 70.0)
        self.declare_parameter('person_lidar_sector_deg', 18.0)
        self.declare_parameter('target_distance_m', 0.95)
        self.declare_parameter('distance_deadzone_m', 0.18)
        self.declare_parameter('min_follow_distance_m', 0.45)
        self.declare_parameter('lidar_distance_gain', 0.24)
        self.declare_parameter('scan_timeout_sec', 0.8)
        self.declare_parameter('status_topic', '/follow/status')
        self.declare_parameter('status_rate_hz', 2.0)

        # Get parameters
        self.image_width = self.get_parameter('image_width').value
        self.image_height = self.get_parameter('image_height').value
        self.center_x_gain = self.get_parameter('center_x_gain').value
        self.height_gain = self.get_parameter('height_gain').value
        self.target_height_ratio = self.get_parameter('target_height_ratio').value
        self.max_linear_vel = self.get_parameter('max_linear_velocity').value
        self.max_angular_vel = self.get_parameter('max_angular_velocity').value
        self.min_linear_vel = float(self.get_parameter('min_linear_velocity').value)
        self.deadzone_center = self.get_parameter('deadzone_center').value
        self.deadzone_height = self.get_parameter('deadzone_height').value
        self.follow_enabled_topic = self.get_parameter('follow_enabled_topic').value
        self.bbox_timeout_sec = float(self.get_parameter('bbox_timeout_sec').value)
        self.max_source_age_sec = max(0.0, float(self.get_parameter('max_source_age_sec').value))
        self.min_detection_confidence = float(self.get_parameter('min_detection_confidence').value)
        self.command_rate_hz = max(1.0, float(self.get_parameter('command_rate_hz').value))
        self.linear_accel_limit = max(0.01, float(self.get_parameter('linear_accel_limit').value))
        self.angular_accel_limit = max(0.01, float(self.get_parameter('angular_accel_limit').value))
        self.bbox_smoothing_alpha = min(1.0, max(0.0, float(self.get_parameter('bbox_smoothing_alpha').value)))
        self.bbox_filter_reset_sec = max(0.0, float(self.get_parameter('bbox_filter_reset_sec').value))
        self.allow_reverse = bool(self.get_parameter('allow_reverse').value)
        self.visible_forward_velocity = max(0.0, float(self.get_parameter('visible_forward_velocity').value))
        self.visible_forward_center_deadzone = max(0.0, float(self.get_parameter('visible_forward_center_deadzone').value))
        self.visible_forward_max_height_ratio = max(
            0.0,
            float(self.get_parameter('visible_forward_max_height_ratio').value),
        )
        self.use_lidar_distance = bool(self.get_parameter('use_lidar_distance').value)
        self.scan_topic = str(self.get_parameter('scan_topic').value)
        self.scan_forward_center_deg = float(self.get_parameter('scan_forward_center_deg').value)
        self.camera_horizontal_fov_deg = max(1.0, float(self.get_parameter('camera_horizontal_fov_deg').value))
        self.person_lidar_sector_deg = max(1.0, float(self.get_parameter('person_lidar_sector_deg').value))
        self.target_distance_m = max(0.05, float(self.get_parameter('target_distance_m').value))
        self.distance_deadzone_m = max(0.0, float(self.get_parameter('distance_deadzone_m').value))
        self.min_follow_distance_m = max(0.0, float(self.get_parameter('min_follow_distance_m').value))
        self.lidar_distance_gain = max(0.0, float(self.get_parameter('lidar_distance_gain').value))
        self.scan_timeout_sec = max(0.0, float(self.get_parameter('scan_timeout_sec').value))
        self.status_topic = str(self.get_parameter('status_topic').value)
        self.status_rate_hz = max(0.2, float(self.get_parameter('status_rate_hz').value))

        # Calculate target height in pixels
        self.target_height = self.image_height * self.target_height_ratio
        self.visible_forward_max_height = self.image_height * self.visible_forward_max_height_ratio

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
        self.status_publisher = self.create_publisher(
            String, self.status_topic, command_qos)

        # Subscriber for person bounding box
        self.bbox_subscriber = self.create_subscription(
            Float32MultiArray, '/vision/person_bbox', self.bbox_callback, bbox_qos)
        self.scan_subscriber = self.create_subscription(
            LaserScan, self.scan_topic, self.scan_callback, bbox_qos)
        self.follow_enabled_subscriber = self.create_subscription(
            Bool, self.follow_enabled_topic, self.follow_enabled_callback, command_qos)
        self.command_timer = self.create_timer(1.0 / self.command_rate_hz, self.command_timer_callback)
        self.status_timer = self.create_timer(1.0 / self.status_rate_hz, self.status_timer_callback)

        # State
        self.last_bbox_time = self.get_clock().now()
        self.last_command_time = self.get_clock().now()
        self.has_bbox = False
        self.last_raw_bbox = None
        self.filtered_bbox = None
        self.last_source_image_age_sec = None
        self.last_reject_reason = "waiting_for_bbox"
        self.last_control_reason = "waiting_for_bbox"
        self.latest_scan = None
        self.last_scan_time = None
        self.last_lidar_distance_m = None
        self.target_twist = Twist()
        self.current_twist = Twist()
        self.following_active = False
        self.follow_enabled = False
        self.last_command_was_nonzero = False
        self._stale_logged = False

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
        self.get_logger().info(f"  Min linear velocity: {self.min_linear_vel}")
        self.get_logger().info(f"  Deadzones: center={self.deadzone_center}px, height={self.deadzone_height}px")
        self.get_logger().info(f"  Follow enable topic: {self.follow_enabled_topic}")
        self.get_logger().info(f"  BBox timeout: {self.bbox_timeout_sec:.2f}s")
        self.get_logger().info(f"  Max source image age: {self.max_source_age_sec:.2f}s")
        self.get_logger().info(f"  Min detection confidence: {self.min_detection_confidence:.2f}")
        self.get_logger().info(f"  Command rate: {self.command_rate_hz:.1f}Hz")
        self.get_logger().info(f"  Accel limits: linear={self.linear_accel_limit}/s angular={self.angular_accel_limit}/s")
        self.get_logger().info(f"  BBox smoothing alpha: {self.bbox_smoothing_alpha:.2f}")
        self.get_logger().info(f"  Allow reverse: {self.allow_reverse}")
        self.get_logger().info(
            f"  Visible forward: velocity={self.visible_forward_velocity}, "
            f"center_deadzone={self.visible_forward_center_deadzone}px, "
            f"max_height={self.visible_forward_max_height:.0f}px"
        )
        self.get_logger().info(
            f"  LiDAR distance: enabled={self.use_lidar_distance} topic={self.scan_topic} "
            f"target={self.target_distance_m:.2f}m deadzone={self.distance_deadzone_m:.2f}m "
            f"min={self.min_follow_distance_m:.2f}m sector={self.person_lidar_sector_deg:.1f}deg"
        )
        self.get_logger().info(f"  Status topic: {self.status_topic} at {self.status_rate_hz:.1f}Hz")

    def scan_callback(self, msg: LaserScan):
        """Store the freshest LiDAR scan for camera-bearing distance control."""
        self.latest_scan = msg
        self.last_scan_time = self.get_clock().now()

    def follow_enabled_callback(self, msg: Bool):
        """Enable or disable following based on external control."""
        new_state = bool(msg.data)
        if new_state == self.follow_enabled:
            return

        self.follow_enabled = new_state
        if not new_state:
            self.following_active = False
            self.filtered_bbox = None
            self._publish_zero_velocity("follow disabled")
        else:
            self._stale_logged = False
            self.last_command_time = self.get_clock().now()
            self.last_reject_reason = "waiting_for_bbox"

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
            source_image_age_sec = float(msg.data[5]) if len(msg.data) >= 6 else 0.0
            if float(confidence) < self.min_detection_confidence:
                self.last_reject_reason = f"low_confidence:{float(confidence):.3f}"
                self.get_logger().debug(f"Ignoring low-confidence detection: {confidence:.2f}")
                return
            if self.max_source_age_sec > 0.0 and source_image_age_sec > self.max_source_age_sec:
                self.following_active = False
                self.target_twist = Twist()
                self.last_source_image_age_sec = source_image_age_sec
                self.last_reject_reason = f"stale_image:{source_image_age_sec:.2f}s"
                self.get_logger().debug(
                    f"Ignoring stale detection from image age {source_image_age_sec:.2f}s"
                )
                return

            # Update state
            now = self.get_clock().now()
            previous_age = (
                (now - self.last_bbox_time).nanoseconds / 1e9
                if self.has_bbox
                else None
            )
            raw_bbox = {
                "x": float(x),
                "y": float(y),
                "width": float(width),
                "height": float(height),
                "confidence": float(confidence),
                "source_image_age_sec": source_image_age_sec,
            }
            smoothed_bbox = self._smooth_bbox(raw_bbox, previous_age)

            self.last_raw_bbox = raw_bbox
            self.last_source_image_age_sec = source_image_age_sec
            self.filtered_bbox = smoothed_bbox
            self.has_bbox = True
            self.last_bbox_time = now
            self.following_active = True
            self._stale_logged = False
            self.last_reject_reason = "tracking"

            # Compute control commands
            twist = self._compute_follow_velocity(
                smoothed_bbox["x"],
                smoothed_bbox["y"],
                smoothed_bbox["width"],
                smoothed_bbox["height"],
            )

            # Store the target; the command timer publishes a smoothed stream.
            self.target_twist = twist

            self.get_logger().debug(
                f"Following person: raw_x={x:.0f}, smooth_x={smoothed_bbox['x']:.0f}, "
                f"raw_height={height:.0f}, smooth_height={smoothed_bbox['height']:.0f}, "
                f"vx={twist.linear.x:.3f}, wz={twist.angular.z:.3f}"
            )

        except Exception as e:
            self.get_logger().error(f"Error processing bbox: {e}")

    def command_timer_callback(self):
        """Publish a smooth command stream so detector cadence does not cause stop/go motion."""
        if not self.follow_enabled:
            if self.last_command_was_nonzero:
                self._publish_zero_velocity("follow disabled watchdog")
            return

        if self.following_active:
            elapsed = (self.get_clock().now() - self.last_bbox_time).nanoseconds / 1e9
            if elapsed > self.bbox_timeout_sec:
                self.following_active = False
                self.target_twist = Twist()
                self.last_reject_reason = "bbox_timeout"
                if not self._stale_logged:
                    self.get_logger().debug(f"BBox stale after {elapsed:.2f}s; ramping follow command to zero")
                    self._stale_logged = True
        elif self._is_zero_twist(self.current_twist):
            return
        else:
            self.target_twist = Twist()

        now = self.get_clock().now()
        dt = min(0.25, max(0.001, (now - self.last_command_time).nanoseconds / 1e9))
        self.last_command_time = now
        self.current_twist = self._ramp_twist(self.current_twist, self.target_twist, dt)
        self._publish_twist(self.current_twist)

    def status_timer_callback(self):
        """Publish compact follow-controller diagnostics for the panel/debug bundle."""
        self._publish_status()

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

        lidar_distance = self._person_lidar_distance(center_offset)
        linear_reason = "height_deadzone"
        used_lidar_distance = lidar_distance is not None

        if used_lidar_distance:
            self.last_lidar_distance_m = lidar_distance
            if abs(center_offset) > self.visible_forward_center_deadzone:
                linear_reason = f"lidar_wait_center:{lidar_distance:.2f}m"
            elif lidar_distance <= self.min_follow_distance_m:
                linear_reason = f"lidar_too_close:{lidar_distance:.2f}m"
            else:
                distance_error = lidar_distance - self.target_distance_m
                if abs(distance_error) <= self.distance_deadzone_m:
                    linear_reason = f"lidar_distance_hold:{lidar_distance:.2f}m"
                else:
                    linear_vel = distance_error * self.lidar_distance_gain
                    linear_reason = "lidar_forward" if linear_vel > 0.0 else "lidar_reverse"
                    if abs(linear_vel) > 1e-4:
                        sign = 1.0 if linear_vel > 0 else -1.0
                        linear_vel = sign * max(abs(linear_vel), self.min_linear_vel)
                    linear_vel = max(-self.max_linear_vel, min(self.max_linear_vel, linear_vel))
                    if not self.allow_reverse and linear_vel < 0.0:
                        linear_vel = 0.0
                        linear_reason = f"lidar_reverse_blocked:{lidar_distance:.2f}m"
                    twist.linear.x = linear_vel

        # Calculate height error (negative = too far, positive = too close).
        # Use this only as a fallback when LiDAR cannot provide a fresh distance.
        height_error = bbox_height - self.target_height

        # Apply deadzone for height control
        if not used_lidar_distance and abs(height_error) > self.deadzone_height:
            # Linear velocity proportional to height error
            # Negative height_error means person is far, so move forward (positive vx)
            linear_vel = -height_error * self.height_gain
            linear_reason = "height_forward" if linear_vel > 0.0 else "height_too_close"

            # Enforce a small minimum duty cycle to overcome gearbox stiction.
            # The command timer ramps up to this floor instead of jumping to it.
            if abs(linear_vel) > 1e-4:
                sign = 1.0 if linear_vel > 0 else -1.0
                linear_vel = sign * max(abs(linear_vel), self.min_linear_vel)

            # Limit linear velocity
            linear_vel = max(-self.max_linear_vel, min(self.max_linear_vel, linear_vel))
            if not self.allow_reverse and linear_vel < 0.0:
                linear_vel = 0.0
                linear_reason = "reverse_blocked"
            twist.linear.x = linear_vel

        if (
            not used_lidar_distance
            and self.visible_forward_velocity > 0.0
            and twist.linear.x <= 1e-4
            and abs(center_offset) <= self.visible_forward_center_deadzone
            and bbox_height <= self.visible_forward_max_height
        ):
            twist.linear.x = min(self.max_linear_vel, max(self.visible_forward_velocity, self.min_linear_vel))
            linear_reason = f"visible_forward_after_{linear_reason}"

        self.last_control_reason = (
            f"{linear_reason},height={bbox_height:.0f}/{self.target_height:.0f},"
            f"offset={center_offset:.0f},lidar={self._format_optional_float(lidar_distance)}"
        )
        return twist

    def _person_lidar_distance(self, center_offset: float) -> float | None:
        if not self.use_lidar_distance or self.latest_scan is None or self.last_scan_time is None:
            return None

        scan_age = (self.get_clock().now() - self.last_scan_time).nanoseconds / 1e9
        if self.scan_timeout_sec > 0.0 and scan_age > self.scan_timeout_sec:
            return None

        msg = self.latest_scan
        bearing_ratio = center_offset / max(1.0, self.image_width / 2.0)
        bearing_deg = max(-1.0, min(1.0, bearing_ratio)) * (self.camera_horizontal_fov_deg / 2.0)
        center_deg = self.scan_forward_center_deg + bearing_deg
        half_sector = self.person_lidar_sector_deg / 2.0
        return self._scan_sector_min(msg, center_deg, -half_sector, half_sector)

    def _scan_sector_min(self, msg: LaserScan, center_deg: float, start_offset_deg: float, end_offset_deg: float) -> float | None:
        center_rad = math.radians(center_deg)
        start_rad = math.radians(min(start_offset_deg, end_offset_deg))
        end_rad = math.radians(max(start_offset_deg, end_offset_deg))
        values = []

        angle = float(msg.angle_min)
        for raw_distance in msg.ranges:
            distance = float(raw_distance)
            relative_angle = math.atan2(math.sin(angle - center_rad), math.cos(angle - center_rad))
            if start_rad <= relative_angle <= end_rad:
                if math.isfinite(distance) and msg.range_min < distance < msg.range_max:
                    values.append(distance)
            angle += float(msg.angle_increment)

        if not values:
            return None
        return min(values)

    @staticmethod
    def _format_optional_float(value: float | None) -> str:
        if value is None:
            return "none"
        return f"{value:.2f}"

    def _smooth_bbox(self, raw_bbox: dict, previous_age: float | None) -> dict:
        if (
            self.filtered_bbox is None
            or previous_age is None
            or previous_age > self.bbox_filter_reset_sec
            or self.bbox_smoothing_alpha >= 1.0
        ):
            return dict(raw_bbox)

        alpha = self.bbox_smoothing_alpha
        beta = 1.0 - alpha
        return {
            "x": alpha * raw_bbox["x"] + beta * self.filtered_bbox["x"],
            "y": alpha * raw_bbox["y"] + beta * self.filtered_bbox["y"],
            "width": alpha * raw_bbox["width"] + beta * self.filtered_bbox["width"],
            "height": alpha * raw_bbox["height"] + beta * self.filtered_bbox["height"],
            "confidence": raw_bbox["confidence"],
            "source_image_age_sec": raw_bbox.get("source_image_age_sec", 0.0),
        }

    def _ramp_twist(self, current: Twist, target: Twist, dt: float) -> Twist:
        smoothed = Twist()
        smoothed.linear.x = self._approach(
            current.linear.x,
            target.linear.x,
            self.linear_accel_limit * dt,
        )
        smoothed.linear.y = self._approach(
            current.linear.y,
            target.linear.y,
            self.linear_accel_limit * dt,
        )
        smoothed.angular.z = self._approach(
            current.angular.z,
            target.angular.z,
            self.angular_accel_limit * dt,
        )
        return smoothed

    @staticmethod
    def _approach(current: float, target: float, max_delta: float) -> float:
        delta = target - current
        if abs(delta) <= max_delta:
            return target
        return current + math.copysign(max_delta, delta)

    def _is_zero_twist(self, twist: Twist) -> bool:
        return (
            abs(twist.linear.x) < 1e-4
            and abs(twist.linear.y) < 1e-4
            and abs(twist.angular.z) < 1e-4
        )

    def _publish_zero_velocity(self, reason: str):
        zero_twist = Twist()
        self.target_twist = Twist()
        self.current_twist = Twist()
        self._publish_twist(zero_twist)
        self.last_command_time = self.get_clock().now()
        self.get_logger().debug(f"Published zero follow velocity: {reason}")

    def _publish_twist(self, twist: Twist):
        self.cmd_publisher.publish(twist)
        self.last_command_was_nonzero = False
        if not self._is_zero_twist(twist):
            self.last_command_was_nonzero = True

    def _publish_status(self):
        msg = String()
        msg.data = json.dumps(self._status_payload(), ensure_ascii=False)
        self.status_publisher.publish(msg)

    def _status_payload(self) -> dict:
        bbox_age_sec = None
        if self.has_bbox:
            bbox_age_sec = max(0.0, (self.get_clock().now() - self.last_bbox_time).nanoseconds / 1e9)

        return {
            "enabled": bool(self.follow_enabled),
            "state": self._state_label(bbox_age_sec),
            "tracking_active": bool(self.following_active),
            "bbox_age_sec": round(bbox_age_sec, 3) if bbox_age_sec is not None else None,
            "last_reject_reason": self.last_reject_reason,
            "raw_bbox": self._round_bbox(self.last_raw_bbox),
            "filtered_bbox": self._round_bbox(self.filtered_bbox),
            "target_cmd": self._twist_payload(self.target_twist),
            "current_cmd": self._twist_payload(self.current_twist),
            "control_reason": self.last_control_reason,
            "lidar_distance_m": round(float(self.last_lidar_distance_m), 3) if self.last_lidar_distance_m is not None else None,
            "params": {
                "center_x_gain": self.center_x_gain,
                "height_gain": self.height_gain,
                "target_height_ratio": self.target_height_ratio,
                "max_linear_velocity": self.max_linear_vel,
                "max_angular_velocity": self.max_angular_vel,
                "min_linear_velocity": self.min_linear_vel,
                "bbox_timeout_sec": self.bbox_timeout_sec,
                "max_source_age_sec": self.max_source_age_sec,
                "command_rate_hz": self.command_rate_hz,
                "linear_accel_limit": self.linear_accel_limit,
                "angular_accel_limit": self.angular_accel_limit,
                "bbox_smoothing_alpha": self.bbox_smoothing_alpha,
                "allow_reverse": self.allow_reverse,
                "visible_forward_velocity": self.visible_forward_velocity,
                "visible_forward_center_deadzone": self.visible_forward_center_deadzone,
                "visible_forward_max_height_ratio": self.visible_forward_max_height_ratio,
                "use_lidar_distance": self.use_lidar_distance,
                "target_distance_m": self.target_distance_m,
                "distance_deadzone_m": self.distance_deadzone_m,
                "min_follow_distance_m": self.min_follow_distance_m,
                "lidar_distance_gain": self.lidar_distance_gain,
            },
        }

    def _state_label(self, bbox_age_sec: float | None) -> str:
        if not self.follow_enabled:
            return "disabled"
        if self.following_active:
            return "tracking"
        if not self._is_zero_twist(self.current_twist):
            return "stopping"
        if bbox_age_sec is None:
            return "searching"
        if bbox_age_sec > self.bbox_timeout_sec:
            return "stale"
        return "armed"

    @staticmethod
    def _twist_payload(twist: Twist) -> dict:
        return {
            "linear_x": round(float(twist.linear.x), 3),
            "linear_y": round(float(twist.linear.y), 3),
            "angular_z": round(float(twist.angular.z), 3),
        }

    @staticmethod
    def _round_bbox(bbox: dict | None) -> dict | None:
        if bbox is None:
            return None
        return {
            "x": round(float(bbox.get("x", 0.0)), 2),
            "y": round(float(bbox.get("y", 0.0)), 2),
            "width": round(float(bbox.get("width", 0.0)), 2),
            "height": round(float(bbox.get("height", 0.0)), 2),
            "confidence": round(float(bbox.get("confidence", 0.0)), 3),
            "source_image_age_sec": round(float(bbox.get("source_image_age_sec", 0.0)), 3),
        }

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
