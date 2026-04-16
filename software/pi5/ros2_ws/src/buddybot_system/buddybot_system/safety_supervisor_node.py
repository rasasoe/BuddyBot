#!/usr/bin/env python3
"""
Safety Supervisor Node for BuddyBot.

Aggregates hard-stop safety sources. LiDAR avoidance is handled separately as a
soft safety override in command_mux, but a severe obstacle state can still latch
the system safety topic here.
"""

import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import Bool, String


class SafetySupervisorNode(Node):
    def __init__(self):
        super().__init__("safety_supervisor_node")

        self.declare_parameter("command_timeout", 1.0)
        self.declare_parameter("safety_latch_time", 2.0)
        self.declare_parameter("health_check_rate", 5.0)

        self.command_timeout = self.get_parameter("command_timeout").value
        self.safety_latch_time = self.get_parameter("safety_latch_time").value
        self.health_check_rate = self.get_parameter("health_check_rate").value

        self.safety_active = False
        self.safety_sources = {
            "estop_button": {"active": False, "timestamp": 0, "description": "Physical E-Stop"},
            "pico_safety": {"active": False, "timestamp": 0, "description": "Pico Safety Event"},
            "ttc_alert": {"active": False, "timestamp": 0, "description": "Time-to-Collision"},
            "command_timeout": {"active": False, "timestamp": 0, "description": "Command Timeout"},
            "system_health": {"active": False, "timestamp": 0, "description": "System Health"},
            "lidar_blocked": {"active": False, "timestamp": 0, "description": "LiDAR Blocked"},
        }

        self.last_command_time = time.time()
        self.safety_trigger_time = 0
        self.last_command_status = "unknown"
        self.last_lidar_status = "unknown"

        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            depth=1,
        )

        self.safety_publisher = self.create_publisher(Bool, "/system/safety_active", qos_profile)
        self.safety_status_publisher = self.create_publisher(String, "/system/safety_status", qos_profile)

        self.create_subscription(Bool, "/system/estop", self.estop_callback, qos_profile)
        self.create_subscription(String, "/buddybot/pico_safety_event", self.pico_safety_callback, qos_profile)
        self.create_subscription(String, "/vision/ttc_alert", self.ttc_callback, qos_profile)
        self.create_subscription(String, "/system/command_status", self.command_status_callback, qos_profile)
        self.create_subscription(String, "/system/lidar_avoidance_status", self.lidar_status_callback, qos_profile)

        self.timer = self.create_timer(1.0 / self.health_check_rate, self.timer_callback)
        self._publish_safety_state()

    def estop_callback(self, msg: Bool):
        self._update_safety_source("estop_button", msg.data)

    def pico_safety_callback(self, msg: String):
        if msg.data:
            self.get_logger().warn(f"Pico safety event: {msg.data}")
            self._update_safety_source("pico_safety", True)

    def ttc_callback(self, msg: String):
        if msg.data.startswith("ttc:"):
            try:
                ttc_value = float(msg.data.split(":")[1])
                safety_trigger = ttc_value < 1.0
                self._update_safety_source("ttc_alert", safety_trigger)
            except (ValueError, IndexError):
                self.get_logger().error(f"Invalid TTC message format: {msg.data}")

    def lidar_status_callback(self, msg: String):
        self.last_lidar_status = msg.data or "unknown"
        active = msg.data.startswith("avoid_stop:")
        self._update_safety_source("lidar_blocked", active)

    def command_status_callback(self, msg: String):
        current_time = time.time()
        self.last_command_status = msg.data or "unknown"
        if current_time - self.last_command_time > self.command_timeout:
            self._update_safety_source("command_timeout", True)
        else:
            self._update_safety_source("command_timeout", False)
        self.last_command_time = current_time

    def _update_safety_source(self, source_id: str, active: bool):
        if source_id in self.safety_sources:
            old_state = self.safety_sources[source_id]["active"]
            self.safety_sources[source_id]["active"] = active
            self.safety_sources[source_id]["timestamp"] = time.time()
            if active != old_state:
                status = "activated" if active else "cleared"
                self.get_logger().info(f"Safety source {source_id} {status}")
            self._evaluate_safety_state()

    def _evaluate_safety_state(self):
        new_safety_state = any(source["active"] for source in self.safety_sources.values())

        if new_safety_state and not self.safety_active:
            self.safety_active = True
            self.safety_trigger_time = time.time()
            active_sources = [sid for sid, s in self.safety_sources.items() if s["active"]]
            self.get_logger().warn(
                f"SYSTEM SAFETY ACTIVATED: {active_sources} command={self.last_command_status} lidar={self.last_lidar_status}"
            )

        elif not new_safety_state and self.safety_active:
            if time.time() - self.safety_trigger_time > self.safety_latch_time:
                self.safety_active = False
                self.get_logger().info(
                    f"SYSTEM SAFETY CLEARED command={self.last_command_status} lidar={self.last_lidar_status}"
                )

        self._publish_safety_state()

    def _publish_safety_state(self):
        safety_msg = Bool()
        safety_msg.data = self.safety_active
        self.safety_publisher.publish(safety_msg)

        active_sources = [sid for sid, s in self.safety_sources.items() if s["active"]]
        status_msg = String()
        command_status = self.last_command_status.replace(",", "|")
        lidar_status = self.last_lidar_status.replace(",", "|")
        status_msg.data = (
            f"active:{self.safety_active},sources:{','.join(active_sources)},"
            f"command:{command_status},lidar:{lidar_status}"
        )
        self.safety_status_publisher.publish(status_msg)

    def timer_callback(self):
        self._evaluate_safety_state()

    def destroy_node(self):
        safety_msg = Bool()
        safety_msg.data = True
        self.safety_publisher.publish(safety_msg)
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    try:
        node = SafetySupervisorNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        rclpy.shutdown()


if __name__ == "__main__":
    main()
