#!/usr/bin/env python3
"""
Voice interface bridge for BuddyBot.

This node does not perform speech recognition by itself.
Instead, it accepts recognized text on `/voice/text`, forwards the text to the
BuddyBot AI server, and republishes the response on `/voice/response`.
"""

import requests
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class VoiceInterface(Node):
    def __init__(self):
        super().__init__("voice_interface")
        self.declare_parameter("buddybot_ai_url", "http://127.0.0.1:8000")
        self.buddybot_ai_url = self.get_parameter("buddybot_ai_url").value.rstrip("/")

        self.response_pub = self.create_publisher(String, "/voice/response", 10)
        self.command_pub = self.create_publisher(String, "/voice/command_status", 10)
        self.create_subscription(String, "/voice/text", self.text_callback, 10)

        self.get_logger().info(
            f"Voice interface bridge ready. Forwarding /voice/text to {self.buddybot_ai_url}/chat"
        )

    def text_callback(self, msg: String) -> None:
        user_text = msg.data.strip()
        if not user_text:
            return

        self._publish_status(f"received:{user_text}")

        try:
            response = requests.post(
                f"{self.buddybot_ai_url}/chat",
                json={"message": user_text},
                timeout=15,
            )
            response.raise_for_status()
            answer = response.json().get("response", "").strip()
            if not answer:
                answer = "응답이 비어 있습니다."

            out = String()
            out.data = answer
            self.response_pub.publish(out)
            self._publish_status("response_published")
            self.get_logger().info(f"Voice request handled: {user_text} -> {answer}")
        except requests.RequestException as exc:
            error_message = f"voice_bridge_error:{exc}"
            self._publish_status(error_message)
            self.get_logger().error(error_message)

    def _publish_status(self, text: str) -> None:
        msg = String()
        msg.data = text
        self.command_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = VoiceInterface()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
