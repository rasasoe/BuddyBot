#!/usr/bin/env python3
"""
Voice Interface Node

This node provides local voice interface for BuddyBot.
It listens for wake word and voice commands, publishing them for mode manager.
Safety: Voice commands are processed through the command mux for safety.
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import speech_recognition as sr
import threading

class VoiceInterface(Node):
    def __init__(self):
        super().__init__('voice_interface')
        self.wake_publisher = self.create_publisher(String, 'voice_trigger', 10)
        self.command_publisher = self.create_publisher(String, 'voice_command_text', 10)
        
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        
        # Calibrate for ambient noise
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source)
        
        self.wake_word = 'buddy'
        self.listening = False
        
        # Start listening thread
        self.thread = threading.Thread(target=self.listen_loop)
        self.thread.daemon = True
        self.thread.start()

    def listen_loop(self):
        while rclpy.ok():
            with self.microphone as source:
                try:
                    audio = self.recognizer.listen(source, timeout=1, phrase_time_limit=5)
                    text = self.recognizer.recognize_google(audio).lower()
                    
                    if self.wake_word in text:
                        wake_msg = String()
                        wake_msg.data = 'wake_word'
                        self.wake_publisher.publish(wake_msg)
                        self.listening = True
                        self.get_logger().info('Wake word detected')
                    elif self.listening:
                        # Process command
                        cmd_msg = String()
                        cmd_msg.data = text
                        self.command_publisher.publish(cmd_msg)
                        self.listening = False
                        
                except sr.WaitTimeoutError:
                    pass
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    self.get_logger().error(f'Speech recognition error: {e}')

def main(args=None):
    rclpy.init(args=args)
    node = VoiceInterface()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()