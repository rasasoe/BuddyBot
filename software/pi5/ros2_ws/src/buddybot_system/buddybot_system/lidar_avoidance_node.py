#!/usr/bin/env python3
"""
LiDAR-based obstacle avoidance node for BuddyBot.

This node listens to LaserScan data and publishes a safety override velocity when
an obstacle is detected in the commanded driving direction. The goal is not full
autonomous path planning, but a practical safety layer for demos:

- clear path: no override
- caution distance: slow turn away from obstacle
- stop distance: stronger turn in place

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
from std_msgs.msg import String


class LidarAvoidanceNode(Node):
    def __init__(self):
        super().__init__("lidar_avoidance_node")

        self.declare_parameter("scan_topic", "/scan")
        self.declare_parameter("command_timeout", 0.6)
        self.declare_parameter("front_angle_deg", 30.0)
        self.declare_parameter("side_angle_deg", 75.0)
        self.declare_parameter("caution_distance", 0.65)
        self.declare_parameter("stop_distance", 0.34)
        self.declare_parameter("turn_speed", 0.55)
        self.declare_parameter("reverse_speed", 0.08)
        self.declare_parameter("check_rate", 15.0)

        self.scan_topic = self.get_parameter("scan_topic").value
        self.command_timeout = float(self.get_parameter("command_timeout").value)
        self.front_angle_deg = float(self.get_parameter("front_angle_deg").value)
        self.side_angle_deg = float(self.get_parameter("side_angle_deg").value)
        self.caution_distance = float(self.get_parameter("caution_distance").value)
        self.stop_distance = float(self.get_parameter("stop_distance").value)
        self.turn_speed = float(self.get_parameter("turn_speed").value)
        self.reverse_speed = float(self.get_parameter("reverse_speed").value)
        self.check_rate = float(self.get_parameter("check_rate").value)

        control_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            depth=10,
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

        front = self._sector_min(-self.front_angle_deg, self.front_angle_deg)
        left = self._sector_min(self.front_angle_deg, self.side_angle_deg)
        right = self._sector_min(-self.side_angle_deg, -self.front_angle_deg)

        if front is None:
            self._clear_override("front_unknown")
            return

        if front >= self.caution_distance:
            self._clear_override(f"clear:{front:.2f}")
            return

        override = Twist()
        turn_left = right is not None and left is not None and right < left

        if front < self.stop_distance:
            override.linear.x = -self.reverse_speed if self.latest_command.linear.x > 0.0 else 0.0
            override.angular.z = -self.turn_speed if turn_left else self.turn_speed
            status = (
                f"avoid_stop:front={front:.2f},left={left},right={right},source={self.latest_command_source},"
                f"cmd={self._format_command(self.latest_command)}"
            )
        else:
            override.linear.x = 0.0
            override.angular.z = -self.turn_speed * 0.75 if turn_left else self.turn_speed * 0.75
            status = (
                f"avoid_turn:front={front:.2f},left={left},right={right},source={self.latest_command_source},"
                f"cmd={self._format_command(self.latest_command)}"
            )

        self.override_pub.publish(override)
        self.override_active = True
        self._publish_status(status)

    def _sector_min(self, start_deg: float, end_deg: float) -> Optional[float]:
        if self.latest_scan is None:
            return None

        msg = self.latest_scan
        start_rad = math.radians(start_deg)
        end_rad = math.radians(end_deg)
        values: List[float] = []

        for index, distance in enumerate(msg.ranges):
            angle = msg.angle_min + index * msg.angle_increment
            if angle < start_rad or angle > end_rad:
                continue
            if math.isfinite(distance) and msg.range_min < distance < msg.range_max:
                values.append(distance)

        if not values:
            return None
        return min(values)

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
