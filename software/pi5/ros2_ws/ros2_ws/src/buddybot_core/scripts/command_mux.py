#!/usr/bin/env python3
"""
Command Multiplexer Node

This node acts as the central command multiplexer for BuddyBot.
It receives velocity commands from various sources (navigation, person following, voice control)
and selects the appropriate command based on the current mode and priorities.
Safety: Ensures that emergency stop commands take precedence over all others.
"""

import rclpy
from rclpy.node import Node
from buddybot_msgs.msg import Command
from std_msgs.msg import String

class CommandMux(Node):
    def __init__(self):
        super().__init__('command_mux')
        self.publisher = self.create_publisher(Command, 'velocity_command', 10)
        
        # Subscribers for different command sources
        self.nav_sub = self.create_subscription(
            Command, 'nav_command', self.nav_callback, 10)
        self.follow_sub = self.create_subscription(
            Command, 'follow_command', self.follow_callback, 10)
        self.voice_sub = self.create_subscription(
            Command, 'voice_command', self.voice_callback, 10)
        
        # Mode subscriber
        self.mode_sub = self.create_subscription(
            String, 'robot_mode', self.mode_callback, 10)
        
        # Emergency stop subscriber
        self.emergency_sub = self.create_subscription(
            Command, 'emergency_stop', self.emergency_callback, 10)
        
        self.current_mode = 'idle'
        self.nav_cmd = Command()
        self.follow_cmd = Command()
        self.voice_cmd = Command()
        self.emergency_cmd = Command()
        
        # Timer to publish selected command
        self.timer = self.create_timer(0.1, self.timer_callback)  # 10Hz

    def nav_callback(self, msg):
        self.nav_cmd = msg

    def follow_callback(self, msg):
        self.follow_cmd = msg

    def voice_callback(self, msg):
        self.voice_cmd = msg

    def mode_callback(self, msg):
        self.current_mode = msg.data

    def emergency_callback(self, msg):
        # Emergency stop: zero velocities
        self.emergency_cmd.linear_x = 0.0
        self.emergency_cmd.linear_y = 0.0
        self.emergency_cmd.angular_z = 0.0

    def timer_callback(self):
        cmd = Command()
        
        # Priority: Emergency > Voice > Follow > Nav
        if self.emergency_cmd.linear_x == 0.0 and self.emergency_cmd.linear_y == 0.0:
            if self.current_mode == 'voice':
                cmd = self.voice_cmd
            elif self.current_mode == 'follow':
                cmd = self.follow_cmd
            elif self.current_mode == 'nav':
                cmd = self.nav_cmd
            # else idle: zero cmd
        
        self.publisher.publish(cmd)

def main(args=None):
    rclpy.init(args=args)
    node = CommandMux()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()