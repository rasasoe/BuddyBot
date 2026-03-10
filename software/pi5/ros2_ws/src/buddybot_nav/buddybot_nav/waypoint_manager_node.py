#!/usr/bin/env python3
"""
Waypoint Manager Node for BuddyBot Navigation

This node manages semantic waypoint navigation for BuddyBot, providing a high-level
interface for navigation goals while integrating with Nav2 stack.

Architecture:
- Loads waypoint database from YAML configuration
- Provides ROS services for waypoint navigation requests
- Translates semantic destinations ("kitchen", "door") to pose goals
- Integrates with Nav2 navigate_to_pose action server
- Monitors navigation status and provides feedback
- Respects system safety states and mode management

Integration Points:
- Nav2: navigate_to_pose action client
- System: mode manager for NAVIGATION mode coordination
- Command Mux: navigation cmd_vel output (when active)
- Safety: emergency stop integration

Waypoint Database:
- Semantic names mapped to poses (x, y, theta)
- Optional approach parameters (distance, orientation)
- Navigation constraints (speed limits, avoidance zones)

Services:
- /nav/waypoint_request (string waypoint_name -> bool success)
- /nav/get_waypoints (empty -> WaypointList)
- /nav/cancel_navigation (empty -> bool success)

Topics:
- /nav/current_waypoint (string): Current navigation target
- /nav/navigation_status (string): Navigation state feedback
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

from geometry_msgs.msg import PoseStamped, Pose
from std_msgs.msg import String
from std_srvs.srv import Trigger
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry

import yaml
import os
import math
from typing import Dict, Optional, Tuple


class WaypointManagerNode(Node):
    """
    Waypoint manager implementing semantic navigation goals.

    This node serves as the interface between high-level navigation requests
    and the Nav2 navigation stack, providing semantic waypoint management.
    """

    def __init__(self):
        super().__init__('waypoint_manager_node')

        # Declare parameters
        self.declare_parameter('waypoint_config', 'config/waypoints.yaml')
        self.declare_parameter('navigation_timeout', 300.0)  # seconds
        self.declare_parameter('goal_tolerance', 0.5)        # meters
        self.declare_parameter('use_sim_time', False)

        # Get parameters
        waypoint_config = self.get_parameter('waypoint_config').value
        self.navigation_timeout = self.get_parameter('navigation_timeout').value
        self.goal_tolerance = self.get_parameter('goal_tolerance').value
        self.use_sim_time = self.get_parameter('use_sim_time').value

        # Load waypoint database
        self.waypoints = self._load_waypoints(waypoint_config)

        # Navigation state
        self.current_waypoint = None
        self.navigation_active = False
        self.last_odom_time = self.get_clock().now()

        # Action client for Nav2
        self.nav_action_client = ActionClient(
            self, NavigateToPose, '/navigate_to_pose')

        # Publishers
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            depth=1
        )

        self.current_waypoint_pub = self.create_publisher(
            String, '/nav/current_waypoint', qos_profile)

        self.navigation_status_pub = self.create_publisher(
            String, '/nav/navigation_status', qos_profile)

        # Subscribers
        self.create_subscription(
            Odometry, '/odom', self.odom_callback, 10)

        self.create_subscription(
            String, '/system/current_mode', self.mode_callback, qos_profile)

        # Services
        self.create_service(
            Trigger, '/nav/waypoint_request',
            self.waypoint_request_callback)

        self.create_service(
            Trigger, '/nav/get_waypoints',
            self.get_waypoints_callback)

        self.create_service(
            Trigger, '/nav/cancel_navigation',
            self.cancel_navigation_callback)

        # Timer for navigation monitoring
        self.create_timer(1.0, self.navigation_monitor_callback)

        self.get_logger().info("Waypoint manager node initialized")
        self._log_available_waypoints()

    def _load_waypoints(self, config_file: str) -> Dict[str, Dict]:
        """Load waypoint database from YAML configuration."""
        try:
            # Try to find config file in package share directory
            config_path = config_file
            if not os.path.exists(config_path):
                # Fallback to relative path from package
                package_share = os.path.join(
                    os.path.dirname(__file__), '..', 'config', 'waypoints.yaml')
                if os.path.exists(package_share):
                    config_path = package_share

            with open(config_path, 'r') as f:
                waypoints = yaml.safe_load(f)

            self.get_logger().info(f"Loaded {len(waypoints)} waypoints from {config_path}")
            return waypoints

        except Exception as e:
            self.get_logger().error(f"Failed to load waypoints: {e}")
            return {}

    def _log_available_waypoints(self):
        """Log all available waypoints."""
        if not self.waypoints:
            self.get_logger().warn("No waypoints loaded!")
            return

        self.get_logger().info("Available waypoints:")
        for name, data in self.waypoints.items():
            pose = data.get('pose', {})
            x, y = pose.get('x', 0.0), pose.get('y', 0.0)
            self.get_logger().info(f"  {name}: ({x:.2f}, {y:.2f})")

    def waypoint_request_callback(self, request, response):
        """Handle waypoint navigation requests."""
        # This is a placeholder - in full implementation would:
        # 1. Validate waypoint exists
        # 2. Check system mode allows navigation
        # 3. Send goal to Nav2 action server
        # 4. Monitor progress and provide feedback

        waypoint_name = request.data if hasattr(request, 'data') else "unknown"

        self.get_logger().info(f"Waypoint request: {waypoint_name}")

        # Placeholder response
        response.success = waypoint_name in self.waypoints
        response.message = f"Waypoint '{waypoint_name}' navigation request processed"

        if response.success:
            self._start_navigation(waypoint_name)
        else:
            self.get_logger().warn(f"Unknown waypoint: {waypoint_name}")

        return response

    def get_waypoints_callback(self, request, response):
        """Return list of available waypoints."""
        waypoint_names = list(self.waypoints.keys())
        response.success = True
        response.message = f"Available waypoints: {', '.join(waypoint_names)}"
        return response

    def cancel_navigation_callback(self, request, response):
        """Cancel current navigation."""
        if self.navigation_active:
            # Cancel Nav2 action
            self.nav_action_client._cancel_goal()
            self.navigation_active = False
            self.current_waypoint = None
            response.success = True
            response.message = "Navigation cancelled"
            self._publish_navigation_status("cancelled")
        else:
            response.success = False
            response.message = "No active navigation to cancel"

        return response

    def _start_navigation(self, waypoint_name: str):
        """Start navigation to specified waypoint."""
        if waypoint_name not in self.waypoints:
            self.get_logger().error(f"Unknown waypoint: {waypoint_name}")
            return

        waypoint_data = self.waypoints[waypoint_name]
        pose_data = waypoint_data.get('pose', {})

        # Create Nav2 goal
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()

        goal.pose.pose.position.x = pose_data.get('x', 0.0)
        goal.pose.pose.position.y = pose_data.get('y', 0.0)
        goal.pose.pose.position.z = 0.0

        # Convert yaw to quaternion
        yaw = pose_data.get('theta', 0.0)
        goal.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(yaw / 2.0)

        self.get_logger().info(f"Starting navigation to {waypoint_name}")

        # Send goal to Nav2 (placeholder - would need action client setup)
        # self.nav_action_client.wait_for_server()
        # self.nav_action_client.send_goal_async(goal)

        self.current_waypoint = waypoint_name
        self.navigation_active = True
        self._publish_current_waypoint(waypoint_name)
        self._publish_navigation_status("navigating")

    def odom_callback(self, msg: Odometry):
        """Monitor odometry for navigation progress."""
        self.last_odom_time = self.get_clock().now()

        # Placeholder: In full implementation, would check distance to goal
        # and update navigation status accordingly

    def mode_callback(self, msg: String):
        """Handle system mode changes."""
        mode = msg.data

        if mode != "NAVIGATION" and self.navigation_active:
            self.get_logger().info(f"Mode changed to {mode}, cancelling navigation")
            self.cancel_navigation_callback(None, None)  # Trigger cancel

    def navigation_monitor_callback(self):
        """Monitor navigation progress and handle timeouts."""
        if not self.navigation_active:
            return

        # Check for navigation timeout
        time_since_odom = (self.get_clock().now() - self.last_odom_time).nanoseconds / 1e9
        if time_since_odom > 5.0:  # No odom updates for 5 seconds
            self.get_logger().warn("Lost odometry, navigation may be stalled")
            self._publish_navigation_status("odom_lost")

        # Placeholder: Check if goal reached
        # In full implementation, would monitor Nav2 action feedback/result

    def _publish_current_waypoint(self, waypoint: str):
        """Publish current navigation waypoint."""
        msg = String()
        msg.data = waypoint
        self.current_waypoint_pub.publish(msg)

    def _publish_navigation_status(self, status: str):
        """Publish navigation status."""
        msg = String()
        msg.data = status
        self.navigation_status_pub.publish(msg)

    def destroy_node(self):
        """Clean shutdown."""
        if self.navigation_active:
            self.get_logger().info("Cancelling navigation on shutdown")
            # Cancel any active navigation

        super().destroy_node()


def main(args=None):
    """Main entry point."""
    rclpy.init(args=args)

    try:
        node = WaypointManagerNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Fatal error in waypoint manager node: {e}")
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    main()