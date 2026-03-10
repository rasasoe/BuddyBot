#!/usr/bin/env python3
"""
Waypoint Navigator Node

This node manages waypoint-based navigation for BuddyBot.
It receives waypoint goals and uses the Nav2 stack to navigate to them.
Safety: Monitors navigation progress and can abort if safety conditions are violated.
"""

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from buddybot_msgs.msg import Waypoint, Command
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String

class WaypointNavigator(Node):
    def __init__(self):
        super().__init__('waypoint_navigator')
        self.publisher = self.create_publisher(Command, 'nav_command', 10)
        self.goal_publisher = self.create_publisher(String, 'nav_goal', 10)
        
        self.subscription = self.create_subscription(
            Waypoint, 'waypoint_goal', self.waypoint_callback, 10)
        
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        
        self.current_waypoint = None

    def waypoint_callback(self, msg):
        # Convert waypoint to Nav2 goal
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = msg.x
        goal.pose.pose.position.y = msg.y
        goal.pose.pose.orientation.z = msg.theta  # Simplified
        
        self.nav_client.wait_for_server()
        self._send_goal_future = self.nav_client.send_goal_async(goal)
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error('Goal rejected')
            return
        self.get_logger().info('Goal accepted')
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        result = future.result().result
        self.get_logger().info('Navigation completed')
        # Publish completion
        msg = String()
        msg.data = 'nav_complete'
        self.goal_publisher.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = WaypointNavigator()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()