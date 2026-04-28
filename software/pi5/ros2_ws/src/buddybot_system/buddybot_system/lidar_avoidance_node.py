#!/usr/bin/env python3
"""
LiDAR-based obstacle avoidance node for BuddyBot.

This node listens to LaserScan data and publishes a safety override velocity when
an obstacle is detected in the commanded driving direction. The goal is not full
autonomous path planning, but a practical safety layer for demos:

- clear path: no override
- caution distance: sidestep away from obstacle
- stop distance: reverse and sidestep escape

The override is consumed by command_mux_node with higher priority than follow/nav
and manual motion, but lower than latched emergency stop.
"""

from __future__ import annotations

import math
import time
from typing import List, Optional

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, String


class LidarAvoidanceNode(Node):
    def __init__(self):
        super().__init__("lidar_avoidance_node")

        self.declare_parameter("scan_topic", "/scan")
        self.declare_parameter("command_timeout", 0.6)
        self.declare_parameter("forward_center_deg", 180.0)
        self.declare_parameter("front_angle_deg", 42.0)
        self.declare_parameter("side_angle_deg", 120.0)
        self.declare_parameter("caution_distance", 0.72)
        self.declare_parameter("stop_distance", 0.40)
        self.declare_parameter("hard_stop_distance", 0.20)
        self.declare_parameter("turn_speed", 0.36)
        self.declare_parameter("reverse_speed", 0.06)
        self.declare_parameter("escape_strafe_speed", 0.16)
        self.declare_parameter("check_rate", 15.0)
        self.declare_parameter("manual_avoidance_enabled", False)

        self.scan_topic = self.get_parameter("scan_topic").value
        self.command_timeout = float(self.get_parameter("command_timeout").value)
        self.forward_center_deg = float(self.get_parameter("forward_center_deg").value)
        self.front_angle_deg = float(self.get_parameter("front_angle_deg").value)
        self.side_angle_deg = float(self.get_parameter("side_angle_deg").value)
        self.caution_distance = float(self.get_parameter("caution_distance").value)
        self.stop_distance = float(self.get_parameter("stop_distance").value)
        self.hard_stop_distance = float(self.get_parameter("hard_stop_distance").value)
        self.turn_speed = float(self.get_parameter("turn_speed").value)
        self.reverse_speed = float(self.get_parameter("reverse_speed").value)
        self.escape_strafe_speed = float(self.get_parameter("escape_strafe_speed").value)
        self.check_rate = float(self.get_parameter("check_rate").value)
        self.manual_avoidance_enabled = bool(self.get_parameter("manual_avoidance_enabled").value)

        control_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            depth=10,
        )
        state_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            depth=1,
        )
        scan_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            depth=10,
        )

        self.override_pub = self.create_publisher(Twist, "/cmd_vel_safety_override", control_qos)
        self.status_pub = self.create_publisher(String, "/system/lidar_avoidance_status", control_qos)

        self.create_subscription(LaserScan, self.scan_topic, self.scan_callback, scan_qos)
        self.create_subscription(Twist, "/cmd_vel_follow", self.follow_callback, control_qos)
        self.create_subscription(Twist, "/cmd_vel_nav", self.nav_callback, control_qos)
        self.create_subscription(Twist, "/cmd_vel_manual", self.manual_callback, control_qos)
        self.create_subscription(Bool, "/system/manual_avoidance_enabled", self.manual_avoidance_callback, state_qos)

        self.latest_scan: Optional[LaserScan] = None
        self.latest_command = Twist()
        self.latest_command_source = "idle"
        self.latest_command_time = 0.0
        self.override_active = False
        self.last_status = "idle"

        self.timer = self.create_timer(1.0 / self.check_rate, self.timer_callback)
        self.get_logger().info("LiDAR avoidance node initialized")

    def scan_callback(self, msg: LaserScan) -> None:
        self.latest_scan = msg

    def follow_callback(self, msg: Twist) -> None:
        self._store_command("follow", msg)

    def nav_callback(self, msg: Twist) -> None:
        self._store_command("nav", msg)

    def manual_callback(self, msg: Twist) -> None:
        self._store_command("manual", msg)

    def manual_avoidance_callback(self, msg: Bool) -> None:
        self.manual_avoidance_enabled = bool(msg.data)

    def _store_command(self, source: str, msg: Twist) -> None:
        self.latest_command = msg
        self.latest_command_source = source
        self.latest_command_time = time.time()

    def _format_command(self, msg: Twist) -> str:
        return f"{msg.linear.x:.3f}/{msg.linear.y:.3f}/{msg.angular.z:.3f}"

    def timer_callback(self) -> None:
        if self.latest_scan is None:
            self._clear_override("scan_missing")
            return

        if time.time() - self.latest_command_time > self.command_timeout:
            self._clear_override("command_idle")
            return

        if self._is_zero_twist(self.latest_command):
            self._clear_override("robot_idle")
            return

        if self.latest_command_source == "manual" and not self.manual_avoidance_enabled:
            self._clear_override("manual_bypass")
            return

        center_deg = self._command_center_deg(self.latest_command)
        front = self._sector_min_relative(center_deg, -self.front_angle_deg, self.front_angle_deg)
        left = self._sector_min_relative(center_deg, self.front_angle_deg, self.side_angle_deg)
        right = self._sector_min_relative(center_deg, -self.side_angle_deg, -self.front_angle_deg)
        rear = self._sector_min_relative(center_deg + 180.0, -self.front_angle_deg, self.front_angle_deg)

        if front is None:
            self._clear_override("front_unknown")
            return

        if front >= self.caution_distance:
            self._clear_override(f"clear:{front:.2f}")
            return

        override = Twist()
        turn_negative = self._prefer_negative_turn(left, right)
        escape_sign = -1.0 if turn_negative else 1.0
        left_open = float("inf") if left is None else float(left)
        right_open = float("inf") if right is None else float(right)

        if (
            front < self.hard_stop_distance
            and left_open < self.stop_distance
            and right_open < self.stop_distance
        ):
            self._publish_immediate_stop(
                f"hard_stop:center={center_deg:.1f},front={front:.2f},left={left},right={right},rear={rear},"
                f"source={self.latest_command_source},cmd={self._format_command(self.latest_command)}"
            )
            return

        if front < self.stop_distance:
            self._apply_reverse_vector(override, self.latest_command, scale=1.0)
            self._apply_strafe_escape(override, self.latest_command, escape_sign, scale=1.0)
            override.angular.z = -self.turn_speed if turn_negative else self.turn_speed
            status = (
                f"avoid_escape:center={center_deg:.1f},front={front:.2f},left={left},right={right},rear={rear},"
                f"source={self.latest_command_source},cmd={self._format_command(self.latest_command)}"
            )
        else:
            self._apply_strafe_escape(override, self.latest_command, escape_sign, scale=0.72)
            self._apply_reverse_vector(override, self.latest_command, scale=0.45)
            override.angular.z = -self.turn_speed * 0.58 if turn_negative else self.turn_speed * 0.58
            status = (
                f"avoid_sidestep:center={center_deg:.1f},front={front:.2f},left={left},right={right},rear={rear},"
                f"source={self.latest_command_source},cmd={self._format_command(self.latest_command)}"
            )

        self.override_pub.publish(override)
        self.override_active = True
        self._publish_status(status)

    @staticmethod
    def _normalize_angle_rad(angle: float) -> float:
        return math.atan2(math.sin(angle), math.cos(angle))

    def _sector_min_relative(
        self,
        center_deg: float,
        start_offset_deg: float,
        end_offset_deg: float,
    ) -> Optional[float]:
        if self.latest_scan is None:
            return None

        msg = self.latest_scan
        center_rad = math.radians(center_deg)
        start_rad = math.radians(min(start_offset_deg, end_offset_deg))
        end_rad = math.radians(max(start_offset_deg, end_offset_deg))
        values: List[float] = []

        angle = float(msg.angle_min)
        for raw_distance in msg.ranges:
            distance = float(raw_distance)
            relative_angle = self._normalize_angle_rad(angle - center_rad)
            if start_rad <= relative_angle <= end_rad:
                if math.isfinite(distance) and msg.range_min < distance < msg.range_max:
                    values.append(distance)
            angle += float(msg.angle_increment)

        if not values:
            return None
        return min(values)

    def _command_center_deg(self, msg: Twist) -> float:
        translational_speed = math.hypot(msg.linear.x, msg.linear.y)
        if translational_speed < 0.03:
            return self.forward_center_deg
        motion_heading_deg = math.degrees(math.atan2(msg.linear.y, msg.linear.x))
        return self.forward_center_deg + motion_heading_deg

    def _apply_reverse_vector(self, override: Twist, msg: Twist, scale: float = 1.0) -> None:
        translational_speed = math.hypot(msg.linear.x, msg.linear.y)
        if translational_speed < 1e-4:
            override.linear.x = 0.0
            override.linear.y = 0.0
            return
        reverse_scale = (self.reverse_speed * max(0.0, scale)) / translational_speed
        override.linear.x += -msg.linear.x * reverse_scale
        override.linear.y += -msg.linear.y * reverse_scale

    def _apply_strafe_escape(self, override: Twist, msg: Twist, direction_sign: float, scale: float = 1.0) -> None:
        speed = self.escape_strafe_speed * max(0.0, scale)
        translational_speed = math.hypot(msg.linear.x, msg.linear.y)
        if translational_speed < 0.03:
            override.linear.y += speed if direction_sign >= 0.0 else -speed
            return

        unit_x = msg.linear.x / translational_speed
        unit_y = msg.linear.y / translational_speed
        if direction_sign >= 0.0:
            escape_x = -unit_y
            escape_y = unit_x
        else:
            escape_x = unit_y
            escape_y = -unit_x
        override.linear.x += escape_x * speed
        override.linear.y += escape_y * speed

    def _prefer_negative_turn(self, left: Optional[float], right: Optional[float]) -> bool:
        if left is None and right is None:
            return self.latest_command.angular.z < 0.0
        if left is None:
            return False
        if right is None:
            return True
        return left < right

    def _publish_immediate_stop(self, status: str) -> None:
        self.override_pub.publish(Twist())
        self.override_active = False
        self._publish_status(status)

    def _clear_override(self, status: str) -> None:
        if self.override_active:
            self.override_pub.publish(Twist())
        self.override_active = False
        self._publish_status(status)

    def _publish_status(self, status: str) -> None:
        if status == self.last_status:
            return
        msg = String()
        msg.data = status
        self.status_pub.publish(msg)
        self.last_status = status

    def _is_zero_twist(self, msg: Twist) -> bool:
        return (
            abs(msg.linear.x) < 1e-4
            and abs(msg.linear.y) < 1e-4
            and abs(msg.angular.z) < 1e-4
        )


def main(args=None):
    rclpy.init(args=args)
    try:
        node = LidarAvoidanceNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()


if __name__ == "__main__":
    main()
