from __future__ import annotations

import json
import math
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
    from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
    from nav_msgs.msg import OccupancyGrid, Odometry
    from rclpy.node import Node
    from std_msgs.msg import String

    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    rclpy = None
    PoseWithCovarianceStamped = None
    Twist = None
    OccupancyGrid = None
    Odometry = None
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
    x: Optional[float] = None
    y: Optional[float] = None
    theta: float = 0.0
    description: str = ""


class CurrentPoseWaypointRequest(BaseModel):
    name: str
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
        self._spin_thread = None
        self._manual_pub = None
        self._waypoint_goal_pub = None
        self._waypoint_save_pub = None

        self._lock = threading.Lock()
        self._latest_pose: Optional[Dict[str, float]] = None
        self._latest_map: Optional[Dict[str, Any]] = None
        self._system_status = "idle"

        self._init_ros()

    def _init_ros(self) -> None:
        if not ROS2_AVAILABLE:
            return
        try:
            if not rclpy.ok():
                rclpy.init(args=None)

            self._node = Node("buddybot_local_panel")
            self._manual_pub = self._node.create_publisher(Twist, "/cmd_vel_manual", 10)
            self._waypoint_goal_pub = self._node.create_publisher(String, "/nav/waypoint_goal", 10)
            self._waypoint_save_pub = self._node.create_publisher(String, "/nav/waypoint_save", 10)

            self._node.create_subscription(OccupancyGrid, "/map", self._map_callback, 10)
            self._node.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self._amcl_pose_callback, 10)
            self._node.create_subscription(Odometry, "/odom", self._odom_callback, 10)
            self._node.create_subscription(String, "/system/command_status", self._status_callback, 10)

            self._spin_thread = threading.Thread(target=rclpy.spin, args=(self._node,), daemon=True)
            self._spin_thread.start()
            self.ros2_connected = True
        except Exception:
            self.ros2_connected = False

    def _status_callback(self, msg: String) -> None:
        self._system_status = msg.data

    def _map_callback(self, msg: OccupancyGrid) -> None:
        sampled = self._downsample_occupancy_grid(msg, max_width=220, max_height=220)
        with self._lock:
            self._latest_map = sampled

    def _amcl_pose_callback(self, msg: PoseWithCovarianceStamped) -> None:
        self._update_pose(
            msg.pose.pose.position.x,
            msg.pose.pose.position.y,
            self._yaw_from_quaternion(msg.pose.pose.orientation.z, msg.pose.pose.orientation.w),
            "amcl",
        )

    def _odom_callback(self, msg: Odometry) -> None:
        with self._lock:
            if self._latest_pose is not None and self._latest_pose.get("source") == "amcl":
                return
        self._update_pose(
            msg.pose.pose.position.x,
            msg.pose.pose.position.y,
            self._yaw_from_quaternion(msg.pose.pose.orientation.z, msg.pose.pose.orientation.w),
            "odom",
        )

    def _update_pose(self, x: float, y: float, theta: float, source: str) -> None:
        with self._lock:
            self._latest_pose = {
                "x": round(float(x), 3),
                "y": round(float(y), 3),
                "theta": round(float(theta), 3),
                "source": source,
            }

    def _yaw_from_quaternion(self, z: float, w: float) -> float:
        return math.atan2(2.0 * w * z, 1.0 - 2.0 * z * z)

    def _downsample_occupancy_grid(self, msg: OccupancyGrid, max_width: int, max_height: int) -> Dict[str, Any]:
        width = int(msg.info.width)
        height = int(msg.info.height)
        resolution = float(msg.info.resolution)
        origin_x = float(msg.info.origin.position.x)
        origin_y = float(msg.info.origin.position.y)

        step = max(1, math.ceil(max(width / max_width, height / max_height)))
        sampled_width = max(1, math.ceil(width / step))
        sampled_height = max(1, math.ceil(height / step))
        sampled: List[int] = []
        for row in range(0, height, step):
            for col in range(0, width, step):
                sampled.append(int(msg.data[row * width + col]))

        return {
            "source": "ros_map",
            "width": sampled_width,
            "height": sampled_height,
            "resolution": resolution * step,
            "origin": {"x": origin_x, "y": origin_y},
            "cells": sampled,
        }

    def status(self) -> Dict[str, Any]:
        pose = self.current_pose()
        return {
            "mode": "assistant" if self.assistant_enabled else "standalone",
            "follow_enabled": self.follow_enabled,
            "ros2_connected": self.ros2_connected,
            "server_url": self.server_url,
            "server_connected": self.check_server(),
            "last_command": self.last_command,
            "system_status": self._system_status,
            "map_available": self.map_available(),
            "pose_available": pose is not None,
            "pose": pose,
        }

    def current_pose(self) -> Optional[Dict[str, float]]:
        with self._lock:
            return dict(self._latest_pose) if self._latest_pose is not None else None

    def map_available(self) -> bool:
        with self._lock:
            return self._latest_map is not None

    def get_map_payload(self) -> Dict[str, Any]:
        with self._lock:
            payload = dict(self._latest_map) if self._latest_map is not None else self._build_synthetic_map()
        payload["pose"] = self.current_pose()
        return payload

    def _build_synthetic_map(self) -> Dict[str, Any]:
        waypoints = self.list_waypoints()
        if not waypoints:
            width = 100
            height = 100
            resolution = 0.1
            origin_x = -5.0
            origin_y = -5.0
        else:
            xs = [item["x"] for item in waypoints]
            ys = [item["y"] for item in waypoints]
            padding = 2.0
            origin_x = min(xs) - padding
            origin_y = min(ys) - padding
            max_x = max(xs) + padding
            max_y = max(ys) + padding
            resolution = 0.1
            width = max(60, int(math.ceil((max_x - origin_x) / resolution)))
            height = max(60, int(math.ceil((max_y - origin_y) / resolution)))

        return {
            "source": "synthetic",
            "width": width,
            "height": height,
            "resolution": resolution,
            "origin": {"x": origin_x, "y": origin_y},
            "cells": [0] * (width * height),
        }

    def set_assistant(self, enabled: bool, server_url: str) -> Dict[str, Any]:
        self.assistant_enabled = enabled
        self.server_url = server_url.rstrip("/")
        self.last_command = f"assistant:{'on' if enabled else 'off'}"
        return self.status()

    def check_server(self) -> bool:
        try:
            response = requests.get(f"{self.server_url}/health", timeout=1.2)
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
        text = message.lower().strip()
        if any(keyword in text for keyword in ("정지", "멈춰", "stop", "스톱")):
            self.manual_command("stop", 0.0, 0.0)
            return "로컬 모드에서 정지 명령을 실행했습니다."
        if any(keyword in text for keyword in ("전진", "앞으로", "forward")):
            self.manual_command("forward", 0.35, 1.0)
            return "로컬 모드에서 전진 명령을 실행했습니다."
        if any(keyword in text for keyword in ("후진", "뒤로", "backward")):
            self.manual_command("backward", 0.35, 1.0)
            return "로컬 모드에서 후진 명령을 실행했습니다."
        if any(keyword in text for keyword in ("좌회전", "왼쪽", "left")):
            self.manual_command("left", 0.45, 0.8)
            return "로컬 모드에서 좌회전 명령을 실행했습니다."
        if any(keyword in text for keyword in ("우회전", "오른쪽", "right")):
            self.manual_command("right", 0.45, 0.8)
            return "로컬 모드에서 우회전 명령을 실행했습니다."
        if any(keyword in text for keyword in ("추종 시작", "따라와", "follow")):
            self.follow_enabled = True
            self.last_command = "follow_on"
            return "로컬 모드에서 사용자 추종을 시작 상태로 전환했습니다."
        if any(keyword in text for keyword in ("추종 중지", "추종 멈춰", "follow stop")):
            self.follow_enabled = False
            self.last_command = "follow_off"
            return "로컬 모드에서 사용자 추종을 중지 상태로 전환했습니다."
        if "주방" in text:
            self.go_waypoint("kitchen")
            return "주방 체크포인트로 이동 요청을 보냈습니다."
        if "거실" in text:
            self.go_waypoint("living_room_center")
            return "거실 체크포인트로 이동 요청을 보냈습니다."
        if "충전" in text:
            self.go_waypoint("charging_station")
            return "충전 스테이션으로 이동 요청을 보냈습니다."
        return "로컬 명령 모드입니다. 전진, 후진, 정지, 왼쪽, 오른쪽, 추종 시작, 주방 이동 같은 명령을 사용할 수 있습니다."

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

        def stop_later() -> None:
            self._manual_pub.publish(Twist())

        if direction != "stop":
            timer = threading.Timer(duration, stop_later)
            timer.daemon = True
            timer.start()
        else:
            self._manual_pub.publish(Twist())

    def go_waypoint(self, name: str) -> None:
        self.last_command = f"nav:{name}"
        if self.ros2_connected and self._waypoint_goal_pub is not None:
            msg = String()
            msg.data = name
            self._waypoint_goal_pub.publish(msg)

    def save_waypoint(self, name: str, x: Optional[float], y: Optional[float], theta: float, description: str) -> Dict[str, Any]:
        if x is None or y is None:
            pose = self.current_pose()
            if pose is None:
                raise ValueError("현재 위치가 없어서 좌표 없는 저장을 할 수 없습니다.")
            x = pose["x"]
            y = pose["y"]
            theta = pose["theta"]

        self.last_command = f"save_waypoint:{name}"
        data = self._load_waypoints()
        data.setdefault("waypoints", {})
        data["waypoints"][name] = {
            "pose": {"x": float(x), "y": float(y), "theta": float(theta)},
            "description": description or f"{name} checkpoint",
            "approach_distance": 0.5,
        }
        self._save_waypoints(data)

        if self.ros2_connected and self._waypoint_save_pub is not None:
            msg = String()
            msg.data = json.dumps(
                {"name": name, "x": float(x), "y": float(y), "theta": float(theta), "description": description or name},
                ensure_ascii=True,
            )
            self._waypoint_save_pub.publish(msg)

        return data["waypoints"][name]

    def list_waypoints(self) -> List[Dict[str, Any]]:
        waypoints = self._load_waypoints().get("waypoints", {})
        return [
            {
                "name": name,
                "x": float(item.get("pose", {}).get("x", 0.0)),
                "y": float(item.get("pose", {}).get("y", 0.0)),
                "theta": float(item.get("pose", {}).get("theta", 0.0)),
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


@app.get("/api/map")
def api_map():
    return bridge.get_map_payload()


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
    waypoint = bridge.save_waypoint(request.name, request.x, request.y, request.theta, request.description)
    return {"saved": True, "waypoint": waypoint, "items": bridge.list_waypoints()}


@app.post("/api/waypoints/current")
def api_save_current_waypoint(request: CurrentPoseWaypointRequest):
    waypoint = bridge.save_waypoint(request.name, None, None, 0.0, request.description)
    return {"saved": True, "waypoint": waypoint, "items": bridge.list_waypoints()}


@app.post("/api/go")
def api_go(request: WaypointGoRequest):
    bridge.go_waypoint(request.name)
    return {"success": True, "message": f"{request.name} 체크포인트로 이동 요청을 전송했습니다."}


def main():
    host = os.getenv("BUDDYBOT_PANEL_HOST", "0.0.0.0")
    port = int(os.getenv("BUDDYBOT_PANEL_PORT", "8090"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
