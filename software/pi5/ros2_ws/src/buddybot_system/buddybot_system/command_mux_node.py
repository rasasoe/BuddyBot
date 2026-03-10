#!/usr/bin/env python3
"""
Command Multiplexer Node for BuddyBot

This node serves as the single point of authority for velocity commands in BuddyBot.
It safely arbitrates between multiple command sources with clear priority rules.

Architecture:
- Subscribes to multiple velocity command sources
- Applies strict priority-based selection logic
- Monitors safety state and blocks commands when unsafe
- Publishes final authorized velocity command
- Provides transparent decision logging for debugging

Priority Hierarchy (highest to lowest):
1. Emergency Stop (E-STOP) - Zero velocity, overrides all
2. Manual Stop - User-initiated stop command
3. Safety Override - System safety interventions
4. Navigation Commands - Autonomous navigation
5. Follow Commands - Person following
6. Idle - Default zero velocity state

Safety Design:
- No command source can bypass this multiplexer
- Safety state is continuously monitored
- Invalid or stale commands are rejected
- All decisions are logged for transparency
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool, String
import time


class CommandMuxNode(Node):
    """
    Command multiplexer implementing hierarchical command arbitration.

    This node ensures that only one command source controls the robot at a time,
    with safety mechanisms taking absolute priority over normal operation.
    """

    def __init__(self):
        super().__init__('command_mux_node')

        # Declare parameters
        self.declare_parameter('command_timeout', 0.5)  # seconds
        self.declare_parameter('safety_check_rate', 10.0)  # Hz

        # Get parameters
        self.command_timeout = self.get_parameter('command_timeout').value
        self.safety_check_rate = self.get_parameter('safety_check_rate').value

        # Command source priorities (higher number = higher priority)
        self.PRIORITY_IDLE = 0
        self.PRIORITY_FOLLOW = 1
        self.PRIORITY_NAV = 2
        self.PRIORITY_SAFETY_OVERRIDE = 3
        self.PRIORITY_MANUAL_STOP = 4
        self.PRIORITY_ESTOP = 5

        # Current state
        self.current_priority = self.PRIORITY_IDLE
        self.current_command = Twist()  # Zero velocity
        self.safety_active = False
        self.last_command_time = time.time()

        # Command sources and their timestamps
        self.commands = {
            'idle': {'cmd': Twist(), 'priority': self.PRIORITY_IDLE, 'timestamp': 0, 'active': True},
            'follow': {'cmd': Twist(), 'priority': self.PRIORITY_FOLLOW, 'timestamp': 0, 'active': False},
            'nav': {'cmd': Twist(), 'priority': self.PRIORITY_NAV, 'timestamp': 0, 'active': False},
            'safety_override': {'cmd': Twist(), 'priority': self.PRIORITY_SAFETY_OVERRIDE, 'timestamp': 0, 'active': False},
            'manual_stop': {'cmd': Twist(), 'priority': self.PRIORITY_MANUAL_STOP, 'timestamp': 0, 'active': False},
            'estop': {'cmd': Twist(), 'priority': self.PRIORITY_ESTOP, 'timestamp': time.time(), 'active': True}
        }

        # Publishers
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            depth=1
        )

        self.cmd_publisher = self.create_publisher(
            Twist, '/cmd_vel_final', qos_profile)

        self.status_publisher = self.create_publisher(
            String, '/system/command_status', qos_profile)

        # Subscribers
        self.create_subscription(
            Twist, '/cmd_vel_follow', self.follow_callback, qos_profile)

        self.create_subscription(
            Twist, '/cmd_vel_nav', self.nav_callback, qos_profile)

        self.create_subscription(
            Twist, '/cmd_vel_manual', self.manual_callback, qos_profile)

        self.create_subscription(
            Bool, '/system/safety_active', self.safety_callback, qos_profile)

        # Timer for periodic command evaluation and publishing
        self.timer = self.create_timer(
            1.0 / self.safety_check_rate, self.timer_callback)

        self.get_logger().info("Command multiplexer node initialized")
        self._log_priority_hierarchy()

    def _log_priority_hierarchy(self):
        """Log the command priority hierarchy for transparency."""
        self.get_logger().info("Command Priority Hierarchy:")
        self.get_logger().info("  5: E-STOP (Emergency Stop)")
        self.get_logger().info("  4: Manual Stop")
        self.get_logger().info("  3: Safety Override")
        self.get_logger().info("  2: Navigation")
        self.get_logger().info("  1: Follow")
        self.get_logger().info("  0: Idle")

    def follow_callback(self, msg: Twist):
        """Handle follow command input."""
        self._update_command('follow', msg)

    def nav_callback(self, msg: Twist):
        """Handle navigation command input."""
        self._update_command('nav', msg)

    def manual_callback(self, msg: Twist):
        """Handle manual command input."""
        self._update_command('manual', msg)

    def safety_callback(self, msg: Bool):
        """Handle safety state updates."""
        self.safety_active = msg.data
        if self.safety_active:
            self.get_logger().warn("Safety system activated - blocking all commands")
        else:
            self.get_logger().info("Safety system deactivated - commands enabled")

    def _update_command(self, source: str, cmd: Twist):
        """Update command from a specific source."""
        if source in self.commands:
            self.commands[source]['cmd'] = cmd
            self.commands[source]['timestamp'] = time.time()
            self.commands[source]['active'] = True

            self.get_logger().debug(f"Updated command from {source}: vx={cmd.linear.x:.3f}, wz={cmd.angular.z:.3f}")

    def _evaluate_commands(self):
        """
        Evaluate all available commands and select the highest priority valid one.

        Priority rules:
        1. E-STOP always takes precedence (safety first)
        2. If safety is active, only allow E-STOP or manual stop
        3. Among active commands, select highest priority
        4. Reject stale commands (older than timeout)
        """
        current_time = time.time()
        best_command = None
        best_priority = -1
        selected_source = 'idle'

        # Always consider idle as baseline
        best_command = self.commands['idle']['cmd']
        best_priority = self.commands['idle']['priority']

        for source, data in self.commands.items():
            # Skip inactive sources (except idle and estop which are always considered)
            if not data['active'] and source not in ['idle', 'estop']:
                continue

            # Check command freshness (except for persistent commands like estop)
            if source not in ['idle', 'estop']:
                if current_time - data['timestamp'] > self.command_timeout:
                    self.get_logger().debug(f"Command from {source} is stale, ignoring")
                    continue

            # Apply safety restrictions
            if self.safety_active and data['priority'] < self.PRIORITY_MANUAL_STOP:
                continue  # Only allow stop commands when safety is active

            # Select highest priority command
            if data['priority'] > best_priority:
                best_priority = data['priority']
                best_command = data['cmd']
                selected_source = source

        return best_command, selected_source, best_priority

    def timer_callback(self):
        """Periodic timer callback for command evaluation and publishing."""
        # Evaluate available commands
        selected_cmd, source, priority = self._evaluate_commands()

        # Check if selection changed
        if priority != self.current_priority:
            self.get_logger().info(f"Command source changed to {source} (priority {priority})")
            self.current_priority = priority

        # Publish selected command
        self.cmd_publisher.publish(selected_cmd)

        # Publish status for monitoring
        status_msg = String()
        status_msg.data = f"source:{source},priority:{priority},safety:{self.safety_active}"
        self.status_publisher.publish(status_msg)

        # Update timing
        self.last_command_time = time.time()

        self.get_logger().debug(f"Published command from {source}: vx={selected_cmd.linear.x:.3f}, wz={selected_cmd.angular.z:.3f}")

    def destroy_node(self):
        """Clean shutdown - publish zero velocity."""
        self.get_logger().info("Shutting down command multiplexer")

        # Publish zero velocity on shutdown
        zero_cmd = Twist()
        self.cmd_publisher.publish(zero_cmd)

        super().destroy_node()


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    try:
        node = CommandMuxNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal error in command mux node: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()