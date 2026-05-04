#!/usr/bin/env python3
"""Encoder odometry publisher for the BuddyBot kiwi base."""

import math
from typing import Optional, Tuple

import rclpy
from buddybot_msgs.msg import Status
from geometry_msgs.msg import TransformStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from tf2_ros import TransformBroadcaster


class EncoderOdomNode(Node):
    """Integrate Pico encoder counts into a conservative local odom frame."""

    def __init__(self):
        super().__init__("encoder_odom_node")

        self.declare_parameter("encoder_cpr", 11.0)
        self.declare_parameter("gear_ratio", 270.0)
        self.declare_parameter("wheel_radius_m", 0.05)
        self.declare_parameter("rotation_radius_m", 0.15)
        self.declare_parameter("odom_frame", "odom")
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("publish_tf", True)
        self.declare_parameter("left_encoder_sign", 1.0)
        self.declare_parameter("right_encoder_sign", 1.0)
        self.declare_parameter("back_encoder_sign", 1.0)

        encoder_cpr = float(self.get_parameter("encoder_cpr").value)
        gear_ratio = float(self.get_parameter("gear_ratio").value)
        self.counts_per_rev = max(1.0, encoder_cpr * gear_ratio)
        self.wheel_radius_m = float(self.get_parameter("wheel_radius_m").value)
        self.rotation_radius_m = max(0.01, float(self.get_parameter("rotation_radius_m").value))
        self.odom_frame = str(self.get_parameter("odom_frame").value)
        self.base_frame = str(self.get_parameter("base_frame").value)
        self.publish_tf = bool(self.get_parameter("publish_tf").value)
        self.encoder_signs = (
            float(self.get_parameter("left_encoder_sign").value),
            float(self.get_parameter("right_encoder_sign").value),
            float(self.get_parameter("back_encoder_sign").value),
        )

        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self._last_counts: Optional[Tuple[int, int, int]] = None
        self._last_stamp = None

        self.odom_publisher = self.create_publisher(Odometry, "/odom", 10)
        self.tf_broadcaster = TransformBroadcaster(self) if self.publish_tf else None
        self.status_subscriber = self.create_subscription(
            Status, "/buddybot/pico_status", self._status_callback, 10
        )

        self.get_logger().info(
            "Encoder odom initialized: output_cpr=%.1f wheel_radius=%.3fm rotation_radius=%.3fm"
            % (self.counts_per_rev, self.wheel_radius_m, self.rotation_radius_m)
        )

    def _status_callback(self, msg: Status) -> None:
        counts = (int(msg.left_encoder), int(msg.right_encoder), int(msg.back_encoder))
        stamp = self.get_clock().now()

        if self._last_counts is None:
            self._last_counts = counts
            self._last_stamp = stamp
            self._publish_odom(stamp, 0.0, 0.0, 0.0)
            return

        dt = (stamp - self._last_stamp).nanoseconds / 1e9 if self._last_stamp is not None else 0.0
        deltas = tuple(
            (counts[index] - self._last_counts[index]) * self.encoder_signs[index]
            for index in range(3)
        )
        self._last_counts = counts
        self._last_stamp = stamp

        left_m, right_m, back_m = (self._counts_to_distance(delta) for delta in deltas)
        dx_body, dy_body, dtheta = self._wheel_distances_to_body_delta(left_m, right_m, back_m)

        theta_mid = self.theta + 0.5 * dtheta
        self.x += math.cos(theta_mid) * dx_body - math.sin(theta_mid) * dy_body
        self.y += math.sin(theta_mid) * dx_body + math.cos(theta_mid) * dy_body
        self.theta = self._normalize_angle(self.theta + dtheta)

        vx = dx_body / dt if dt > 0.0 else 0.0
        vy = dy_body / dt if dt > 0.0 else 0.0
        wz = dtheta / dt if dt > 0.0 else 0.0
        self._publish_odom(stamp, vx, vy, wz)

    def _counts_to_distance(self, counts: float) -> float:
        rotations = counts / self.counts_per_rev
        return rotations * (2.0 * math.pi * self.wheel_radius_m)

    def _wheel_distances_to_body_delta(self, left_m: float, right_m: float, back_m: float) -> Tuple[float, float, float]:
        # Inverse of the field-proven direct mix in firmware/kinematics.py:
        # left=vx+0.5*vy+w, right=-vx+0.5*vy+w, back=-vy+w.
        dx = (left_m - right_m) / 2.0
        dy = (left_m + right_m - 2.0 * back_m) / 3.0
        rotation_distance = (left_m + right_m + back_m) / 3.0
        dtheta = rotation_distance / self.rotation_radius_m
        return dx, dy, dtheta

    def _publish_odom(self, stamp, vx: float, vy: float, wz: float) -> None:
        qz = math.sin(self.theta / 2.0)
        qw = math.cos(self.theta / 2.0)

        odom = Odometry()
        odom.header.stamp = stamp.to_msg()
        odom.header.frame_id = self.odom_frame
        odom.child_frame_id = self.base_frame
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.position.z = 0.0
        odom.pose.pose.orientation.z = qz
        odom.pose.pose.orientation.w = qw
        odom.twist.twist.linear.x = vx
        odom.twist.twist.linear.y = vy
        odom.twist.twist.angular.z = wz
        odom.pose.covariance[0] = 0.05
        odom.pose.covariance[7] = 0.05
        odom.pose.covariance[35] = 0.20
        odom.twist.covariance[0] = 0.10
        odom.twist.covariance[7] = 0.10
        odom.twist.covariance[35] = 0.30
        self.odom_publisher.publish(odom)

        if self.tf_broadcaster is not None:
            transform = TransformStamped()
            transform.header.stamp = odom.header.stamp
            transform.header.frame_id = self.odom_frame
            transform.child_frame_id = self.base_frame
            transform.transform.translation.x = self.x
            transform.transform.translation.y = self.y
            transform.transform.translation.z = 0.0
            transform.transform.rotation.z = qz
            transform.transform.rotation.w = qw
            self.tf_broadcaster.sendTransform(transform)

    @staticmethod
    def _normalize_angle(angle: float) -> float:
        while angle > math.pi:
            angle -= 2.0 * math.pi
        while angle < -math.pi:
            angle += 2.0 * math.pi
        return angle


def main(args=None):
    rclpy.init(args=args)
    node = EncoderOdomNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
