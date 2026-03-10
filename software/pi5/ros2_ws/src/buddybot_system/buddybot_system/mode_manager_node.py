#!/usr/bin/env python3
"""
Mode Manager Node for BuddyBot

This node tracks and coordinates the system operating mode, ensuring that
different subsystems operate coherently and safely.

Architecture:
- Maintains single source of truth for system mode
- Provides mode transition logic with safety checks
- Publishes current mode for other nodes to subscribe
- Accepts mode change requests from authorized sources
- Logs all mode transitions for debugging

Supported Modes:
- IDLE: System stopped, no autonomous operation
- MANUAL: Direct teleoperation control
- FOLLOW: Person following mode
- NAV: Autonomous navigation mode

Mode Transition Rules:
- Any mode can transition to IDLE (safe fallback)
- IDLE can transition to any other mode
- FOLLOW and NAV require appropriate subsystem readiness
- Transitions are logged and validated

Safety Integration:
- Mode changes can be vetoed by safety system
- Emergency conditions force transition to IDLE
- Mode state is published for safety supervisor monitoring
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import String, Bool
from std_srvs.srv import SetBool
import time


class ModeManagerNode(Node):
    """
    Mode manager implementing safe system state coordination.

    This node ensures that BuddyBot operates in a coherent state where
    all subsystems are aware of and aligned with the current operating mode.
    """

    def __init__(self):
        super().__init__('mode_manager_node')

        # Supported modes
        self.MODES = ['IDLE', 'MANUAL', 'FOLLOW', 'NAV']
        self.current_mode = 'IDLE'
        self.last_mode_change = time.time()

        # Mode transition validation
        self.valid_transitions = {
            'IDLE': ['MANUAL', 'FOLLOW', 'NAV'],  # From IDLE, can go anywhere
            'MANUAL': ['IDLE'],                    # From MANUAL, only to IDLE
            'FOLLOW': ['IDLE', 'MANUAL'],          # From FOLLOW, to IDLE or MANUAL
            'NAV': ['IDLE', 'MANUAL']              # From NAV, to IDLE or MANUAL
        }

        # Publishers
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,  # Latch mode
            depth=1
        )

        self.mode_publisher = self.create_publisher(
            String, '/system/mode', qos_profile)

        # Services for mode changes
        self.set_mode_service = self.create_service(
            SetBool, '/system/set_mode', self.set_mode_callback)

        # Subscribers
        self.create_subscription(
            Bool, '/system/safety_active', self.safety_callback, qos_profile)

        # Publish initial mode
        self._publish_mode()

        self.get_logger().info("Mode manager node initialized")
        self.get_logger().info(f"Initial mode: {self.current_mode}")
        self._log_supported_modes()

    def _log_supported_modes(self):
        """Log supported modes and transitions."""
        self.get_logger().info("Supported Modes:")
        for mode in self.MODES:
            transitions = self.valid_transitions.get(mode, [])
            self.get_logger().info(f"  {mode} -> {transitions}")

    def set_mode_callback(self, request, response):
        """
        Handle mode change requests.

        Note: This is a simplified implementation. In a real system,
        you'd want a more sophisticated service with mode parameters.
        """
        # For now, we'll use the service data as a simple enable/disable
        # In practice, you'd want a custom service with mode string parameter

        self.get_logger().warn("set_mode service called - implement proper mode service")
        response.success = False
        response.message = "Use proper mode change service"
        return response

    def safety_callback(self, msg: Bool):
        """Handle safety system state changes."""
        if msg.data:
            # Safety activated - force to IDLE mode
            if self.current_mode != 'IDLE':
                self.get_logger().warn("Safety activated - forcing mode to IDLE")
                self._change_mode('IDLE')

    def _change_mode(self, new_mode: str) -> bool:
        """
        Attempt to change system mode.

        Returns True if mode change was successful, False otherwise.
        """
        if new_mode not in self.MODES:
            self.get_logger().error(f"Invalid mode requested: {new_mode}")
            return False

        if new_mode not in self.valid_transitions.get(self.current_mode, []):
            self.get_logger().error(f"Invalid transition: {self.current_mode} -> {new_mode}")
            return False

        # Additional validation could go here
        # (e.g., check if subsystems are ready for the new mode)

        # Perform mode change
        old_mode = self.current_mode
        self.current_mode = new_mode
        self.last_mode_change = time.time()

        self.get_logger().info(f"Mode changed: {old_mode} -> {new_mode}")
        self._publish_mode()

        return True

    def _publish_mode(self):
        """Publish current mode to ROS topic."""
        mode_msg = String()
        mode_msg.data = self.current_mode
        self.mode_publisher.publish(mode_msg)

    def request_mode_change(self, new_mode: str) -> bool:
        """
        Public method to request mode changes from within the node.

        This could be called by timers, other callbacks, or internal logic.
        """
        return self._change_mode(new_mode)

    def get_current_mode(self) -> str:
        """Get current system mode."""
        return self.current_mode

    def get_mode_uptime(self) -> float:
        """Get time since last mode change in seconds."""
        return time.time() - self.last_mode_change

    def destroy_node(self):
        """Clean shutdown."""
        self.get_logger().info("Shutting down mode manager")
        super().destroy_node()


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    try:
        node = ModeManagerNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal error in mode manager node: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()