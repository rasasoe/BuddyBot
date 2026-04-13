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

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, Pose, PoseWithCovarianceStamped, Twist
from std_msgs.msg import String
from std_srvs.srv import Trigger
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry

import yaml
import os
import math
import json
import time
from typing import Dict, List, Optional, Tuple


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
        self.declare_parameter('yaw_tolerance', 0.35)        # rad
        self.declare_parameter('local_nav_rate', 10.0)
        self.declare_parameter('local_position_gain', 0.75)
        self.declare_parameter('local_heading_gain', 1.2)
        self.declare_parameter('max_nav_linear_velocity', 0.3)
        self.declare_parameter('max_nav_angular_velocity', 0.6)
        self.declare_parameter('use_sim_time', False)

        # Get parameters
        waypoint_config = self.get_parameter('waypoint_config').value
        self.waypoint_config = waypoint_config
        self.navigation_timeout = self.get_parameter('navigation_timeout').value
        self.goal_tolerance = self.get_parameter('goal_tolerance').value
        self.yaw_tolerance = float(self.get_parameter('yaw_tolerance').value)
        self.local_nav_rate = float(self.get_parameter('local_nav_rate').value)
        self.local_position_gain = float(self.get_parameter('local_position_gain').value)
        self.local_heading_gain = float(self.get_parameter('local_heading_gain').value)
        self.max_nav_linear_velocity = float(self.get_parameter('max_nav_linear_velocity').value)
        self.max_nav_angular_velocity = float(self.get_parameter('max_nav_angular_velocity').value)
        self.use_sim_time = self.get_parameter('use_sim_time').value

        # Load waypoint database
        self.config_data = self._load_waypoints(waypoint_config)
        self.waypoints = self.config_data.get('waypoints', {})
        self.destinations = self.config_data.get('destinations', {})

        # Navigation state
        self.current_waypoint = None
        self.navigation_active = False
        self.last_odom_time = self.get_clock().now()
        self.current_pose: Optional[Dict[str, float]] = None
        self.current_pose_source = "none"
        self.target_pose: Optional[Dict[str, float]] = None
        self.control_mode = "idle"
        self.goal_handle = None
        self.goal_future = None
        self.result_future = None
        self.navigation_started_at = 0.0
        self.active_destination_name: Optional[str] = None
        self.active_destination_sequence: List[str] = []

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
        self.cmd_vel_nav_pub = self.create_publisher(
            Twist, '/cmd_vel_nav', 10)

        # Subscribers
        self.create_subscription(
            Odometry, '/odom', self.odom_callback, 10)
        self.create_subscription(
            PoseWithCovarianceStamped, '/amcl_pose', self.amcl_pose_callback, 10)

        self.create_subscription(
            String, '/system/current_mode', self.mode_callback, qos_profile)
        self.create_subscription(
            String, '/system/mode', self.mode_callback, qos_profile)
        self.create_subscription(
            String, '/nav/waypoint_goal', self.waypoint_goal_callback, qos_profile)
        self.create_subscription(
            String, '/nav/waypoint_save', self.waypoint_save_callback, qos_profile)
        self.create_subscription(
            String, '/nav/waypoint_delete', self.waypoint_delete_callback, qos_profile)
        self.create_subscription(
            String, '/nav/waypoint_clear', self.waypoint_clear_callback, qos_profile)
        self.create_subscription(
            String, '/nav/destination_goal', self.destination_goal_callback, qos_profile)
        self.create_subscription(
            String, '/nav/destination_save', self.destination_save_callback, qos_profile)
        self.create_subscription(
            String, '/nav/destination_delete', self.destination_delete_callback, qos_profile)
        self.create_subscription(
            String, '/nav/cancel', self.cancel_topic_callback, qos_profile)

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
        self.create_timer(1.0 / self.local_nav_rate, self.local_navigation_callback)

        self.get_logger().info("Waypoint manager node initialized")
        self._log_available_waypoints()
        self._log_available_destinations()

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

            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            waypoints = data.get('waypoints', {})
            self.get_logger().info(f"Loaded {len(waypoints)} waypoints from {config_path}")
            return data

        except Exception as e:
            self.get_logger().error(f"Failed to load waypoints: {e}")
            return {"waypoints": {}, "destinations": {}, "constraints": {}}

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

    def _log_available_destinations(self):
        if not self.destinations:
            self.get_logger().info("No saved routes loaded")
            return

        self.get_logger().info("Available routes:")
        for name, data in self.destinations.items():
            sequence = data.get("sequence", [])
            self.get_logger().info(f"  {name}: {sequence}")

    def waypoint_goal_callback(self, msg: String):
        waypoint_name = msg.data.strip()
        if not waypoint_name:
            return
        if waypoint_name not in self.waypoints:
            self.get_logger().warn(f"Unknown waypoint from topic request: {waypoint_name}")
            self._publish_navigation_status(f"unknown_waypoint:{waypoint_name}")
            return
        self._clear_destination_state()
        self._start_navigation(waypoint_name)

    def waypoint_save_callback(self, msg: String):
        try:
            payload = json.loads(msg.data)
            name = str(payload["name"]).strip()
            if not name:
                raise ValueError("Waypoint name is required")
            self.config_data.setdefault("waypoints", {})
            self.config_data["waypoints"][name] = {
                "pose": {
                    "x": float(payload.get("x", 0.0)),
                    "y": float(payload.get("y", 0.0)),
                    "theta": float(payload.get("theta", 0.0)),
                },
                "description": payload.get("description", f"{name} checkpoint"),
                "approach_distance": float(payload.get("approach_distance", 0.5)),
            }
            self.waypoints = self.config_data["waypoints"]
            self._save_waypoints()
            self._publish_navigation_status(f"waypoint_saved:{name}")
            self.get_logger().info(f"Saved waypoint '{name}'")
        except Exception as exc:
            self.get_logger().error(f"Failed to save waypoint from topic: {exc}")
            self._publish_navigation_status("waypoint_save_failed")

    def waypoint_delete_callback(self, msg: String):
        name = msg.data.strip()
        if not name:
            return
        try:
            self._delete_waypoint(name)
            self._publish_navigation_status(f"waypoint_deleted:{name}")
        except Exception as exc:
            self.get_logger().error(f"Failed to delete waypoint '{name}': {exc}")
            self._publish_navigation_status(f"waypoint_delete_failed:{name}")

    def waypoint_clear_callback(self, msg: String):
        if msg.data.strip() not in {"", "clear"}:
            return
        self._clear_all_waypoints()

    def destination_goal_callback(self, msg: String):
        raw = msg.data.strip()
        if not raw:
            return

        try:
            if raw.startswith("{"):
                payload = json.loads(raw)
                name = str(payload.get("name") or "route_now").strip() or "route_now"
                sequence = self._normalize_sequence(payload.get("sequence", []))
            else:
                name = raw
                destination = self.destinations.get(name)
                if destination is None:
                    self.get_logger().warn(f"Unknown route from topic request: {name}")
                    self._publish_navigation_status(f"unknown_destination:{name}")
                    return
                sequence = self._normalize_sequence(destination.get("sequence", []))

            self._start_destination_sequence(name, sequence)
        except Exception as exc:
            self.get_logger().error(f"Failed to process destination goal: {exc}")
            self._publish_navigation_status("destination_goal_failed")

    def destination_save_callback(self, msg: String):
        try:
            payload = json.loads(msg.data)
            name = str(payload["name"]).strip()
            sequence = self._normalize_sequence(payload.get("sequence", []))
            if not name:
                raise ValueError("Destination name is required")
            if not sequence:
                raise ValueError("Destination sequence is empty")
            missing = [item for item in sequence if item not in self.waypoints]
            if missing:
                raise ValueError(f"Unknown waypoint(s): {', '.join(missing)}")

            self.config_data.setdefault("destinations", {})
            self.config_data["destinations"][name] = {
                "sequence": sequence,
                "description": payload.get("description", f"{name} route"),
            }
            self.destinations = self.config_data["destinations"]
            self._save_waypoints()
            self._publish_navigation_status(f"destination_saved:{name}")
        except Exception as exc:
            self.get_logger().error(f"Failed to save destination from topic: {exc}")
            self._publish_navigation_status("destination_save_failed")

    def destination_delete_callback(self, msg: String):
        name = msg.data.strip()
        if not name:
            return
        destinations = self.config_data.setdefault("destinations", {})
        if name not in destinations:
            self._publish_navigation_status(f"destination_delete_missing:{name}")
            return
        del destinations[name]
        self.destinations = destinations
        if self.active_destination_name == name:
            self._cancel_navigation("destination_deleted")
        self._save_waypoints()
        self._publish_navigation_status(f"destination_deleted:{name}")

    def cancel_topic_callback(self, msg: String):
        if msg.data.strip() or not msg.data:
            self._cancel_navigation("cancelled")

    def _config_path(self) -> str:
        config_path = self.waypoint_config
        if not os.path.isabs(config_path):
            config_path = os.path.join(
                os.path.dirname(__file__), '..', 'config', 'waypoints.yaml')
        return config_path

    def _save_waypoints(self):
        config_path = self._config_path()
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(self.config_data, f, allow_unicode=True, sort_keys=False)

    def _normalize_sequence(self, sequence) -> List[str]:
        return [str(item).strip() for item in sequence if str(item).strip()]

    def _clear_destination_state(self):
        self.active_destination_name = None
        self.active_destination_sequence = []

    def _abort_destination(self, status: str):
        if not self.active_destination_name:
            return
        destination_name = self.active_destination_name
        self._clear_destination_state()
        self._publish_navigation_status(f"destination_failed:{destination_name}:{status}")

    def _delete_waypoint(self, name: str):
        waypoints = self.config_data.setdefault("waypoints", {})
        if name not in waypoints:
            raise ValueError(f"Waypoint '{name}' not found")

        if self.current_waypoint == name and (self.navigation_active or self.goal_handle is not None):
            self._cancel_navigation("waypoint_deleted")

        del waypoints[name]
        self.waypoints = waypoints

        destinations = self.config_data.setdefault("destinations", {})
        updated_destinations = {}
        for destination_name, destination in destinations.items():
            sequence = [item for item in destination.get("sequence", []) if item != name]
            if sequence:
                updated_destinations[destination_name] = {
                    **destination,
                    "sequence": sequence,
                }
            elif self.active_destination_name == destination_name:
                self._clear_destination_state()

        if self.active_destination_sequence:
            self.active_destination_sequence = [item for item in self.active_destination_sequence if item != name]

        self.config_data["destinations"] = updated_destinations
        self.destinations = updated_destinations
        self._save_waypoints()

    def _clear_all_waypoints(self):
        if self.navigation_active or self.goal_handle is not None:
            self._cancel_navigation("waypoints_cleared")

        self.config_data["waypoints"] = {}
        self.config_data["destinations"] = {}
        self.waypoints = {}
        self.destinations = {}
        self._clear_destination_state()
        self._save_waypoints()
        self._publish_navigation_status("waypoints_cleared")

    def _start_destination_sequence(self, name: str, sequence: List[str]):
        cleaned_sequence = self._normalize_sequence(sequence)
        if not cleaned_sequence:
            self._publish_navigation_status(f"destination_empty:{name}")
            return

        missing = [item for item in cleaned_sequence if item not in self.waypoints]
        if missing:
            self._publish_navigation_status(f"destination_missing_waypoint:{name}:{','.join(missing)}")
            return

        if self.navigation_active or self.goal_handle is not None:
            self._cancel_navigation("preempted")

        self.active_destination_name = name
        self.active_destination_sequence = list(cleaned_sequence)
        self._publish_navigation_status(f"destination_started:{name}")
        self._start_next_destination_leg()

    def _start_next_destination_leg(self):
        if not self.active_destination_name:
            return
        if not self.active_destination_sequence:
            completed_name = self.active_destination_name
            self._clear_destination_state()
            self._publish_navigation_status(f"destination_arrived:{completed_name}")
            return

        next_waypoint = self.active_destination_sequence.pop(0)
        self._publish_navigation_status(f"destination_leg:{self.active_destination_name}:{next_waypoint}")
        self._start_navigation(next_waypoint)

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
        if self.navigation_active or self.goal_handle is not None:
            self._cancel_navigation("cancelled")
            response.success = True
            response.message = "Navigation cancelled"
        else:
            response.success = False
            response.message = "No active navigation to cancel"

        return response

    def _start_navigation(self, waypoint_name: str):
        """Start navigation to specified waypoint."""
        if waypoint_name not in self.waypoints:
            self.get_logger().error(f"Unknown waypoint: {waypoint_name}")
            return

        if self.navigation_active or self.goal_handle is not None:
            self._cancel_navigation("preempted")

        waypoint_data = self.waypoints[waypoint_name]
        pose_data = waypoint_data.get('pose', {})
        self.target_pose = {
            "x": float(pose_data.get('x', 0.0)),
            "y": float(pose_data.get('y', 0.0)),
            "theta": float(pose_data.get('theta', 0.0)),
        }

        # Create Nav2 goal
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()

        goal.pose.pose.position.x = self.target_pose["x"]
        goal.pose.pose.position.y = self.target_pose["y"]
        goal.pose.pose.position.z = 0.0

        # Convert yaw to quaternion
        yaw = self.target_pose["theta"]
        goal.pose.pose.orientation.z = math.sin(yaw / 2.0)
        goal.pose.pose.orientation.w = math.cos(yaw / 2.0)

        self.get_logger().info(f"Starting navigation to {waypoint_name}")
        self.current_waypoint = waypoint_name
        self.navigation_started_at = time.time()
        self._publish_current_waypoint(waypoint_name)

        if self.nav_action_client.wait_for_server(timeout_sec=0.5):
            self.navigation_active = True
            self.control_mode = "nav2_pending"
            self.goal_future = self.nav_action_client.send_goal_async(goal)
            self.goal_future.add_done_callback(self._goal_response_callback)
            self._publish_navigation_status(f"navigating_nav2:{waypoint_name}")
            return

        if self.current_pose is None:
            self.get_logger().warn("Nav2 server unavailable and current pose is missing")
            self._publish_navigation_status("pose_unavailable")
            self.current_waypoint = None
            self.target_pose = None
            self._publish_current_waypoint("")
            self._abort_destination("pose_unavailable")
            return

        self.navigation_active = True
        self.control_mode = "local"
        self._publish_navigation_status(f"navigating_local:{waypoint_name}")

    def odom_callback(self, msg: Odometry):
        """Monitor odometry for navigation progress."""
        self.last_odom_time = self.get_clock().now()
        if self.current_pose_source != "amcl":
            self._update_pose(
                msg.pose.pose.position.x,
                msg.pose.pose.position.y,
                self._yaw_from_quaternion(msg.pose.pose.orientation.z, msg.pose.pose.orientation.w),
                "odom",
            )

    def amcl_pose_callback(self, msg: PoseWithCovarianceStamped):
        self._update_pose(
            msg.pose.pose.position.x,
            msg.pose.pose.position.y,
            self._yaw_from_quaternion(msg.pose.pose.orientation.z, msg.pose.pose.orientation.w),
            "amcl",
        )

    def mode_callback(self, msg: String):
        """Handle system mode changes."""
        mode = msg.data.strip().upper()

        if mode not in {"NAV", "NAVIGATION"} and self.navigation_active:
            self.get_logger().info(f"Mode changed to {mode}, cancelling navigation")
            self._cancel_navigation(f"mode_change:{mode}")

    def navigation_monitor_callback(self):
        """Monitor navigation progress and handle timeouts."""
        if not self.navigation_active:
            return

        # Check for navigation timeout
        time_since_odom = (self.get_clock().now() - self.last_odom_time).nanoseconds / 1e9
        if time_since_odom > 5.0:  # No odom updates for 5 seconds
            self.get_logger().warn("Lost odometry, navigation may be stalled")
            self._publish_navigation_status("odom_lost")

        if (time.time() - self.navigation_started_at) > self.navigation_timeout:
            self.get_logger().warn("Navigation timed out")
            self._cancel_navigation("timeout")

    def local_navigation_callback(self):
        if not self.navigation_active or self.control_mode != "local":
            return
        if self.current_pose is None or self.target_pose is None:
            self._cancel_navigation("pose_unavailable")
            return

        dx = self.target_pose["x"] - self.current_pose["x"]
        dy = self.target_pose["y"] - self.current_pose["y"]
        distance = math.hypot(dx, dy)

        if distance <= self.goal_tolerance:
            yaw_error = self._normalize_angle(self.target_pose["theta"] - self.current_pose["theta"])
            if abs(yaw_error) <= self.yaw_tolerance:
                self._publish_nav_velocity(0.0, 0.0, 0.0)
                self._finish_navigation(f"arrived:{self.current_waypoint}")
                return

            angular_z = self._clamp(
                yaw_error * self.local_heading_gain,
                self.max_nav_angular_velocity,
            )
            self._publish_nav_velocity(0.0, 0.0, angular_z)
            return

        theta = self.current_pose["theta"]
        error_x = math.cos(theta) * dx + math.sin(theta) * dy
        error_y = -math.sin(theta) * dx + math.cos(theta) * dy
        yaw_error = self._normalize_angle(self.target_pose["theta"] - theta)

        linear_x = self._clamp(error_x * self.local_position_gain, self.max_nav_linear_velocity)
        linear_y = self._clamp(error_y * self.local_position_gain, self.max_nav_linear_velocity)
        angular_z = self._clamp(yaw_error * self.local_heading_gain, self.max_nav_angular_velocity)

        self._publish_nav_velocity(linear_x, linear_y, angular_z)

    def _goal_response_callback(self, future):
        try:
            goal_handle = future.result()
        except Exception as exc:
            self.get_logger().error(f"Failed to send Nav2 goal: {exc}")
            self.navigation_active = False
            self.control_mode = "idle"
            self._publish_navigation_status("nav2_send_failed")
            self._abort_destination("nav2_send_failed")
            return

        if not goal_handle.accepted:
            self.get_logger().warn("Nav2 goal rejected")
            self.navigation_active = False
            self.control_mode = "idle"
            self.goal_handle = None
            self._publish_navigation_status("nav2_goal_rejected")
            self._publish_current_waypoint("")
            self.current_waypoint = None
            self.target_pose = None
            self._abort_destination("nav2_goal_rejected")
            return

        self.goal_handle = goal_handle
        self.control_mode = "nav2"
        self.result_future = goal_handle.get_result_async()
        self.result_future.add_done_callback(self._nav_result_callback)
        self._publish_navigation_status(f"nav2_active:{self.current_waypoint}")

    def _nav_result_callback(self, future):
        try:
            result = future.result()
            status = result.status
        except Exception as exc:
            self.get_logger().error(f"Failed to receive Nav2 result: {exc}")
            self._finish_navigation("nav2_result_failed")
            return

        if status == GoalStatus.STATUS_SUCCEEDED:
            self._finish_navigation(f"arrived:{self.current_waypoint}")
        elif status == GoalStatus.STATUS_CANCELED:
            self._finish_navigation("cancelled")
        else:
            self._finish_navigation(f"nav2_failed:{status}")

    def _cancel_navigation(self, status: str):
        if self.goal_handle is not None:
            try:
                self.goal_handle.cancel_goal_async()
            except Exception as exc:
                self.get_logger().warn(f"Failed to cancel Nav2 goal cleanly: {exc}")
        self._publish_nav_velocity(0.0, 0.0, 0.0)
        self._finish_navigation(status)

    def _finish_navigation(self, status: str):
        completed_waypoint = self.current_waypoint
        active_destination = self.active_destination_name
        remaining_destination_legs = list(self.active_destination_sequence)

        self.navigation_active = False
        self.control_mode = "idle"
        self.goal_handle = None
        self.goal_future = None
        self.result_future = None
        self.navigation_started_at = 0.0
        self._publish_navigation_status(status)
        self._publish_current_waypoint("")
        self.current_waypoint = None
        self.target_pose = None

        if active_destination:
            if status.startswith("arrived:"):
                if remaining_destination_legs:
                    self._publish_navigation_status(
                        f"destination_progress:{active_destination}:{completed_waypoint}"
                    )
                    self._start_next_destination_leg()
                    return
                self._clear_destination_state()
                self._publish_navigation_status(f"destination_arrived:{active_destination}")
                return

            self._clear_destination_state()
            self._publish_navigation_status(f"destination_failed:{active_destination}:{status}")

    def _publish_nav_velocity(self, linear_x: float, linear_y: float, angular_z: float):
        twist = Twist()
        twist.linear.x = linear_x
        twist.linear.y = linear_y
        twist.angular.z = angular_z
        self.cmd_vel_nav_pub.publish(twist)

    def _update_pose(self, x: float, y: float, theta: float, source: str):
        self.current_pose = {
            "x": float(x),
            "y": float(y),
            "theta": float(theta),
        }
        self.current_pose_source = source

    def _yaw_from_quaternion(self, z: float, w: float) -> float:
        return math.atan2(2.0 * w * z, 1.0 - 2.0 * z * z)

    def _normalize_angle(self, angle: float) -> float:
        while angle > math.pi:
            angle -= 2.0 * math.pi
        while angle < -math.pi:
            angle += 2.0 * math.pi
        return angle

    def _clamp(self, value: float, limit: float) -> float:
        return max(-limit, min(limit, value))

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
        if self.navigation_active or self.goal_handle is not None:
            self.get_logger().info("Cancelling navigation on shutdown")
            self._cancel_navigation("shutdown")

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
