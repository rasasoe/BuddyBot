#!/usr/bin/env python3
"""
Mode Manager Node

This node manages the operational mode of BuddyBot.
Modes include: idle, navigation, person_following, voice_control.
It coordinates mode transitions and ensures safe mode changes.
Safety: Prevents mode changes that could compromise safety.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from buddybot_msgs.msg import Status

class ModeManager(Node):
    def __init__(self):
        super().__init__('mode_manager')
        self.publisher = self.create_publisher(String, 'robot_mode', 10)
        
        # Subscribers
        self.voice_trigger_sub = self.create_subscription(
            String, 'voice_trigger', self.voice_trigger_callback, 10)
        self.nav_goal_sub = self.create_subscription(
            String, 'nav_goal', self.nav_goal_callback, 10)
        self.person_detected_sub = self.create_subscription(
            String, 'person_detected', self.person_detected_callback, 10)
        self.pico_status_sub = self.create_subscription(
            Status, 'pico_status', self.status_callback, 10)
        
        self.current_mode = 'idle'
        self.emergency_active = False
        
        # Timer to publish mode
        self.timer = self.create_timer(1.0, self.timer_callback)

    def voice_trigger_callback(self, msg):
        if msg.data == 'wake_word' and not self.emergency_active:
            self.current_mode = 'voice'

    def nav_goal_callback(self, msg):
        if msg.data == 'start_nav' and not self.emergency_active:
            self.current_mode = 'nav'

    def person_detected_callback(self, msg):
        if msg.data == 'follow' and not self.emergency_active:
            self.current_mode = 'follow'

    def status_callback(self, msg):
        if msg.emergency_stop:
            self.emergency_active = True
            self.current_mode = 'idle'
        else:
            self.emergency_active = False

    def timer_callback(self):
        mode_msg = String()
        mode_msg.data = self.current_mode
        self.publisher.publish(mode_msg)

def main(args=None):
    rclpy.init(args=args)
    node = ModeManager()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()