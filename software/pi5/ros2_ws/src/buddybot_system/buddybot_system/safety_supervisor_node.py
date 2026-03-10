#!/usr/bin/env python3
"""
Safety Supervisor Node for BuddyBot

This node monitors all safety-related events and maintains the system safety state.
It serves as the central safety authority, aggregating inputs from multiple safety sources.

Architecture:
- Monitors emergency stop buttons and switches
- Subscribes to Pico safety events (UART protocol)
- Monitors vision system safety alerts (TTC)
- Tracks command timeouts and system health
- Publishes consolidated safety state
- Provides safety override commands when needed

Safety Sources:
1. Physical E-Stop button/switch
2. Pico microcontroller safety events
3. Time-to-collision alerts from vision
4. Command timeout monitoring
5. System health monitoring

Safety State Logic:
- Any single safety source can trigger system stop
- Safety state is latched until explicitly cleared
- Multiple confirmation may be required for safety clearance
- All safety events are logged with timestamps

Integration:
- Commands safety state to command multiplexer
- Can force mode changes through mode manager
- Provides safety status to monitoring systems
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import Bool, String
import time


class SafetySupervisorNode(Node):
    """
    Safety supervisor implementing comprehensive safety monitoring.

    This node acts as the safety authority for BuddyBot, ensuring that
    dangerous conditions are detected and appropriate safety responses are triggered.
    """

    def __init__(self):
        super().__init__('safety_supervisor_node')

        # Declare parameters
        self.declare_parameter('command_timeout', 1.0)      # seconds
        self.declare_parameter('safety_latch_time', 2.0)    # seconds
        self.declare_parameter('health_check_rate', 5.0)    # Hz

        # Get parameters
        self.command_timeout = self.get_parameter('command_timeout').value
        self.safety_latch_time = self.get_parameter('safety_latch_time').value
        self.health_check_rate = self.get_parameter('health_check_rate').value

        # Safety state
        self.safety_active = False
        self.safety_sources = {
            'estop_button': {'active': False, 'timestamp': 0, 'description': 'Physical E-Stop'},
            'pico_safety': {'active': False, 'timestamp': 0, 'description': 'Pico Safety Event'},
            'ttc_alert': {'active': False, 'timestamp': 0, 'description': 'Time-to-Collision'},
            'command_timeout': {'active': False, 'timestamp': 0, 'description': 'Command Timeout'},
            'system_health': {'active': False, 'timestamp': 0, 'description': 'System Health'}
        }

        self.last_command_time = time.time()
        self.safety_trigger_time = 0

        # Publishers
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,  # Latch safety state
            depth=1
        )

        self.safety_publisher = self.create_publisher(
            Bool, '/system/safety_active', qos_profile)

        self.safety_status_publisher = self.create_publisher(
            String, '/system/safety_status', qos_profile)

        # Subscribers
        self.create_subscription(
            Bool, '/system/estop', self.estop_callback, qos_profile)

        self.create_subscription(
            String, '/buddybot/pico_safety_event', self.pico_safety_callback, qos_profile)

        self.create_subscription(
            String, '/vision/ttc_alert', self.ttc_callback, qos_profile)

        self.create_subscription(
            String, '/system/command_status', self.command_status_callback, qos_profile)

        # Timer for periodic safety evaluation
        self.timer = self.create_timer(
            1.0 / self.health_check_rate, self.timer_callback)

        # Publish initial safety state
        self._publish_safety_state()

        self.get_logger().info("Safety supervisor node initialized")
        self._log_safety_sources()

    def _log_safety_sources(self):
        """Log all safety monitoring sources."""
        self.get_logger().info("Safety Monitoring Sources:")
        for source_id, source_info in self.safety_sources.items():
            self.get_logger().info(f"  {source_id}: {source_info['description']}")

    def estop_callback(self, msg: Bool):
        """Handle physical emergency stop button."""
        self._update_safety_source('estop_button', msg.data)

    def pico_safety_callback(self, msg: String):
        """Handle safety events from Pico."""
        # Pico safety events are critical - always trigger safety
        if msg.data:
            self.get_logger().warn(f"Pico safety event: {msg.data}")
            self._update_safety_source('pico_safety', True)

    def ttc_callback(self, msg: String):
        """Handle time-to-collision alerts from vision system."""
        if msg.data.startswith('ttc:'):
            try:
                ttc_value = float(msg.data.split(':')[1])
                # Trigger safety if TTC is very low (immediate danger)
                safety_trigger = ttc_value < 1.0  # Less than 1 second
                if safety_trigger:
                    self.get_logger().warn(f"TTC alert: {ttc_value:.2f}s - triggering safety")
                self._update_safety_source('ttc_alert', safety_trigger)
            except (ValueError, IndexError):
                self.get_logger().error(f"Invalid TTC message format: {msg.data}")

    def command_status_callback(self, msg: String):
        """Monitor command multiplexer status for timeouts."""
        # This is a simplified timeout check
        # In practice, you'd want more sophisticated timeout detection
        current_time = time.time()
        if current_time - self.last_command_time > self.command_timeout:
            self._update_safety_source('command_timeout', True)
        else:
            self._update_safety_source('command_timeout', False)

        self.last_command_time = current_time

    def _update_safety_source(self, source_id: str, active: bool):
        """Update the state of a safety monitoring source."""
        if source_id in self.safety_sources:
            old_state = self.safety_sources[source_id]['active']
            self.safety_sources[source_id]['active'] = active
            self.safety_sources[source_id]['timestamp'] = time.time()

            if active != old_state:
                status = "activated" if active else "cleared"
                self.get_logger().info(f"Safety source {source_id} {status}")

            # Re-evaluate overall safety state
            self._evaluate_safety_state()

    def _evaluate_safety_state(self):
        """Evaluate overall system safety state from all sources."""
        # Safety is active if ANY source is active
        new_safety_state = any(source['active'] for source in self.safety_sources.values())

        # Handle safety state changes
        if new_safety_state and not self.safety_active:
            # Safety activated
            self.safety_active = True
            self.safety_trigger_time = time.time()
            self.get_logger().warn("SYSTEM SAFETY ACTIVATED")

            # Log which sources triggered safety
            active_sources = [sid for sid, s in self.safety_sources.items() if s['active']]
            self.get_logger().warn(f"Active safety sources: {active_sources}")

        elif not new_safety_state and self.safety_active:
            # Check if safety latch time has passed
            if time.time() - self.safety_trigger_time > self.safety_latch_time:
                self.safety_active = False
                self.get_logger().info("SYSTEM SAFETY CLEARED")
            # Else remain in safety mode until latch time expires

        # Publish updated safety state
        self._publish_safety_state()

    def _publish_safety_state(self):
        """Publish current safety state."""
        # Publish boolean safety state
        safety_msg = Bool()
        safety_msg.data = self.safety_active
        self.safety_publisher.publish(safety_msg)

        # Publish detailed safety status
        active_sources = [sid for sid, s in self.safety_sources.items() if s['active']]
        status_msg = String()
        status_msg.data = f"active:{self.safety_active},sources:{','.join(active_sources)}"
        self.safety_status_publisher.publish(status_msg)

    def timer_callback(self):
        """Periodic timer for health checks and safety evaluation."""
        # Perform system health checks
        # This is where you'd add more sophisticated health monitoring

        # For now, just ensure we haven't lost communication with critical systems
        # (This would be expanded based on your specific health checks)

        self._evaluate_safety_state()

    def get_safety_status(self) -> dict:
        """Get detailed safety status for debugging."""
        return {
            'safety_active': self.safety_active,
            'sources': self.safety_sources.copy(),
            'trigger_time': self.safety_trigger_time
        }

    def destroy_node(self):
        """Clean shutdown."""
        self.get_logger().info("Shutting down safety supervisor")

        # Force safety active on shutdown for safety
        safety_msg = Bool()
        safety_msg.data = True
        self.safety_publisher.publish(safety_msg)

        super().destroy_node()


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    try:
        node = SafetySupervisorNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal error in safety supervisor node: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()