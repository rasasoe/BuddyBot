#!/usr/bin/env python3
"""Priority command multiplexer with safety-first arbitration."""

import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import Bool, String


class CommandMuxNode(Node):
    def __init__(self):
        super().__init__("command_mux_node")
        self.declare_parameter("command_timeout", 0.5)
        self.declare_parameter("safety_check_rate", 10.0)
        self.command_timeout = self.get_parameter("command_timeout").value
        self.safety_check_rate = self.get_parameter("safety_check_rate").value

        self.PRIORITY_IDLE = 0
        self.PRIORITY_FOLLOW = 1
        self.PRIORITY_NAV = 2
        self.PRIORITY_MANUAL = 3
        self.PRIORITY_SAFETY_OVERRIDE = 4
        self.PRIORITY_ESTOP = 5

        self.safety_active = False
        self.estop_latched = False
        self.current_priority = self.PRIORITY_IDLE

        zero = Twist()
        now = time.time()
        self.commands = {
            "idle": {"cmd": zero, "priority": self.PRIORITY_IDLE, "timestamp": now, "active": True},
            "follow": {"cmd": zero, "priority": self.PRIORITY_FOLLOW, "timestamp": 0.0, "active": False},
            "nav": {"cmd": zero, "priority": self.PRIORITY_NAV, "timestamp": 0.0, "active": False},
            "manual": {"cmd": zero, "priority": self.PRIORITY_MANUAL, "timestamp": 0.0, "active": False},
            "safety_override": {"cmd": zero, "priority": self.PRIORITY_SAFETY_OVERRIDE, "timestamp": 0.0, "active": False},
        }

        qos = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, durability=DurabilityPolicy.VOLATILE, depth=1)
        self.cmd_publisher = self.create_publisher(Twist, "/cmd_vel_final", qos)
        self.status_publisher = self.create_publisher(String, "/system/command_status", qos)

        self.create_subscription(Twist, "/cmd_vel_follow", self.follow_callback, qos)
        self.create_subscription(Twist, "/cmd_vel_nav", self.nav_callback, qos)
        self.create_subscription(Twist, "/cmd_vel_manual", self.manual_callback, qos)
        self.create_subscription(Twist, "/cmd_vel_safety_override", self.safety_override_callback, qos)
        self.create_subscription(Bool, "/system/safety_active", self.safety_callback, qos)
        self.create_subscription(Bool, "/system/estop", self.estop_callback, qos)

        self.timer = self.create_timer(1.0 / self.safety_check_rate, self.timer_callback)

    def follow_callback(self, msg):
        self._update_command("follow", msg)

    def nav_callback(self, msg):
        self._update_command("nav", msg)

    def manual_callback(self, msg):
        self._update_command("manual", msg)

    def safety_override_callback(self, msg):
        self._update_command("safety_override", msg)

    def safety_callback(self, msg):
        self.safety_active = msg.data

    def estop_callback(self, msg):
        self.estop_latched = msg.data

    def _is_zero(self, cmd):
        return cmd.linear.x == 0.0 and cmd.linear.y == 0.0 and cmd.angular.z == 0.0

    def _update_command(self, source, cmd):
        if source not in self.commands:
            return
        self.commands[source]["cmd"] = cmd
        self.commands[source]["timestamp"] = time.time()
        self.commands[source]["active"] = not self._is_zero(cmd)

    def _evaluate_commands(self):
        zero = Twist()
        if self.estop_latched:
            return zero, "estop", self.PRIORITY_ESTOP
        if self.safety_active:
            return zero, "safety_latched", self.PRIORITY_SAFETY_OVERRIDE

        now = time.time()
        best_source = "idle"
        best = self.commands["idle"]

        for source in ("follow", "nav", "manual", "safety_override"):
            data = self.commands[source]
            if not data["active"]:
                continue
            if now - data["timestamp"] > self.command_timeout:
                continue
            if data["priority"] > best["priority"]:
                best_source = source
                best = data

        return best["cmd"], best_source, best["priority"]

    def timer_callback(self):
        cmd, source, priority = self._evaluate_commands()
        if priority != self.current_priority:
            self.get_logger().info(f"Command source -> {source} (priority={priority})")
            self.current_priority = priority

        self.cmd_publisher.publish(cmd)
        status = String()
        status.data = f"source:{source},priority:{priority},safety:{self.safety_active},estop:{self.estop_latched}"
        self.status_publisher.publish(status)


def main(args=None):
    rclpy.init(args=args)
    node = CommandMuxNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.cmd_publisher.publish(Twist())
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
