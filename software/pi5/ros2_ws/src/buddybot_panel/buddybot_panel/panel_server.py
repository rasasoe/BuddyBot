from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import uvicorn
import yaml
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    import rclpy
    from geometry_msgs.msg import Twist
    from rclpy.node import Node
    from std_msgs.msg import String

    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    rclpy = None
    Twist = None
    Node = object
    String = object


PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"
WAYPOINT_FILE = (
    PACKAGE_DIR.parent.parent / "buddybot_nav" / "config" / "waypoints.yaml"
).resolve()


class AssistantSettings(BaseModel):
    enabled: bool
    server_url: str


class ChatRequest(BaseModel):
    message: str


class WaypointSaveRequest(BaseModel):
    name: str
    x: float
    y: float
    theta: float = 0.0
    description: str = ""


class WaypointGoRequest(BaseModel):
    name: str


class PanelBridge:
    def __init__(self):
        self.follow_enabled = False
        self.assistant_enabled = False
        self.server_url = os.getenv("BUDDYBOT_AI_URL", "http://127.0.0.1:8000")
        self.last_command = "idle"
        self.ros2_connected = False
        self._node = None
        self._manual_pub = None
        self._waypoint_goal_pub = None
        self._waypoint_save_pub = None
        self._init_ros()

    def _init_ros(self):
        if not ROS2_AVAILABLE:
            return
        try:
            if not rclpy.ok():
                rclpy.init(args=None)
            self._node = Node("buddybot_local_panel")
            self._manual_pub = self._node.create_publisher(Twist, "/cmd_vel_manual", 10)
            self._waypoint_goal_pub = self._node.create_publisher(String, "/nav/waypoint_goal", 10)
            self._waypoint_save_pub = self._node.create_publisher(String, "/nav/waypoint_save", 10)
            self.ros2_connected = True
        except Exception:
            self.ros2_connected = False

    def status(self) -> Dict[str, Any]:
        return {
            "mode": "assistant" if self.assistant_enabled else "standalone",
            "follow_enabled": self.follow_enabled,
            "ros2_connected": self.ros2_connected,
            "server_url": self.server_url,
            "server_connected": self.check_server(),
            "last_command": self.last_command,
        }

    def set_assistant(self, enabled: bool, server_url: str) -> Dict[str, Any]:
        self.assistant_enabled = enabled
        self.server_url = server_url.rstrip("/")
        self.last_command = f"assistant:{'on' if enabled else 'off'}"
        return self.status()

    def check_server(self) -> bool:
        try:
            response = requests.get(f"{self.server_url}/health", timeout=1.5)
            return response.ok
        except requests.RequestException:
            return False

    def handle_chat(self, message: str) -> str:
        if self.assistant_enabled and self.check_server():
            try:
                response = requests.post(
                    f"{self.server_url}/chat",
                    json={"message": message},
                    timeout=20,
                )
                response.raise_for_status()
                return response.json().get("response", "응답이 비어 있습니다.")
            except requests.RequestException:
                pass
        return self._handle_local_command(message)

    def _handle_local_command(self, message: str) -> str:
        text = message.lower()
        if "정지" in text or "stop" in text:
            self.manual_command("stop", 0.0, 0.0)
            return "로컬 모드에서 로봇을 정지했습니다."
        if "앞으로" in text or "전진" in text:
            self.manual_command("forward", 0.35, 1.0)
            return "로컬 모드에서 앞으로 이동합니다."
        if "뒤로" in text or "후진" in text:
            self.manual_command("backward", 0.35, 1.0)
            return "로컬 모드에서 뒤로 이동합니다."
        if "왼쪽" in text:
            self.manual_command("left", 0.35, 0.8)
            return "로컬 모드에서 좌회전합니다."
        if "오른쪽" in text:
            self.manual_command("right", 0.35, 0.8)
            return "로컬 모드에서 우회전합니다."
        if "추종 시작" in text or "따라와" in text:
            self.follow_enabled = True
            self.last_command = "follow_on"
            return "로컬 모드에서 사용자 추종을 시작했습니다."
        if "추종 중지" in text or "따라오지" in text:
            self.follow_enabled = False
            self.last_command = "follow_off"
            return "로컬 모드에서 사용자 추종을 중지했습니다."
        if "주방" in text:
            self.go_waypoint("kitchen")
            return "로컬 모드에서 주방 체크포인트로 이동 요청을 보냈습니다."
        if "거실" in text:
            self.go_waypoint("living_room_center")
            return "로컬 모드에서 거실 체크포인트로 이동 요청을 보냈습니다."
        return "로컬 음성 명령 모드입니다. 전진, 정지, 추종 시작, 주방 이동 같은 명령을 사용할 수 있습니다."

    def manual_command(self, direction: str, speed: float, duration: float) -> None:
        self.last_command = f"manual:{direction}"
        linear_x = 0.0
        angular_z = 0.0
        if direction == "forward":
            linear_x = speed
        elif direction == "backward":
            linear_x = -speed
        elif direction == "left":
            angular_z = speed
        elif direction == "right":
            angular_z = -speed

        if not self.ros2_connected or self._manual_pub is None:
            return

        twist = Twist()
        twist.linear.x = linear_x
        twist.angular.z = angular_z
        self._manual_pub.publish(twist)

        def stop_later():
            zero = Twist()
            self._manual_pub.publish(zero)

        if direction != "stop":
            timer = threading.Timer(duration, stop_later)
            timer.daemon = True
            timer.start()
        else:
            zero = Twist()
            self._manual_pub.publish(zero)

    def go_waypoint(self, name: str) -> None:
        self.last_command = f"nav:{name}"
        if self.ros2_connected and self._waypoint_goal_pub is not None:
            msg = String()
            msg.data = name
            self._waypoint_goal_pub.publish(msg)

    def save_waypoint(self, name: str, x: float, y: float, theta: float, description: str) -> None:
        self.last_command = f"save_waypoint:{name}"
        data = self._load_waypoints()
        data.setdefault("waypoints", {})
        data["waypoints"][name] = {
            "pose": {"x": x, "y": y, "theta": theta},
            "description": description or f"{name} checkpoint",
            "approach_distance": 0.5,
        }
        self._save_waypoints(data)
        if self.ros2_connected and self._waypoint_save_pub is not None:
            msg = String()
            msg.data = (
                f'{{"name":"{name}","x":{x},"y":{y},"theta":{theta},'
                f'"description":"{description or name}"}}'
            )
            self._waypoint_save_pub.publish(msg)

    def list_waypoints(self) -> List[Dict[str, Any]]:
        waypoints = self._load_waypoints().get("waypoints", {})
        return [
            {
                "name": name,
                "x": item.get("pose", {}).get("x", 0.0),
                "y": item.get("pose", {}).get("y", 0.0),
                "theta": item.get("pose", {}).get("theta", 0.0),
                "description": item.get("description", ""),
            }
            for name, item in waypoints.items()
        ]

    def _load_waypoints(self) -> Dict[str, Any]:
        if not WAYPOINT_FILE.exists():
            return {"waypoints": {}, "destinations": {}, "constraints": {}}
        with WAYPOINT_FILE.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {"waypoints": {}, "destinations": {}, "constraints": {}}

    def _save_waypoints(self, data: Dict[str, Any]) -> None:
        with WAYPOINT_FILE.open("w", encoding="utf-8") as file:
            yaml.safe_dump(data, file, allow_unicode=True, sort_keys=False)


bridge = PanelBridge()
app = FastAPI(title="BuddyBot Pi5 Panel")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
def api_status():
    return bridge.status()


@app.post("/api/assistant")
def api_assistant(settings: AssistantSettings):
    return bridge.set_assistant(settings.enabled, settings.server_url)


@app.post("/api/chat")
def api_chat(request: ChatRequest):
    return {"response": bridge.handle_chat(request.message)}


@app.post("/api/manual")
def api_manual(request: Dict[str, Any]):
    bridge.manual_command(request.get("direction", "stop"), float(request.get("speed", 0.35)), float(request.get("duration", 1.0)))
    return bridge.status()


@app.post("/api/follow")
def api_follow(request: Dict[str, Any]):
    bridge.follow_enabled = bool(request.get("enabled", False))
    bridge.last_command = "follow_on" if bridge.follow_enabled else "follow_off"
    return bridge.status()


@app.get("/api/waypoints")
def api_waypoints():
    return {"items": bridge.list_waypoints()}


@app.post("/api/waypoints")
def api_save_waypoint(request: WaypointSaveRequest):
    bridge.save_waypoint(request.name, request.x, request.y, request.theta, request.description)
    return {"saved": True, "items": bridge.list_waypoints()}


@app.post("/api/go")
def api_go(request: WaypointGoRequest):
    bridge.go_waypoint(request.name)
    return {"success": True, "message": f"{request.name} 이동 요청을 전송했습니다."}


def main():
    host = os.getenv("BUDDYBOT_PANEL_HOST", "0.0.0.0")
    port = int(os.getenv("BUDDYBOT_PANEL_PORT", "8090"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
