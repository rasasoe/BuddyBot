from __future__ import annotations

import json
import math
import os
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import requests
import uvicorn
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    import cv2
    import rclpy
    from buddybot_msgs.msg import Status
    from cv_bridge import CvBridge
    from geometry_msgs.msg import PoseWithCovarianceStamped, Twist
    from nav_msgs.msg import OccupancyGrid, Odometry
    from rclpy.executors import SingleThreadedExecutor
    from rclpy.node import Node
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
    from sensor_msgs.msg import Image, LaserScan
    from std_msgs.msg import Bool, String

    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False
    cv2 = None
    rclpy = None
    Status = None
    CvBridge = None
    PoseWithCovarianceStamped = None
    Twist = None
    OccupancyGrid = None
    Odometry = None
    Node = object
    SingleThreadedExecutor = None
    QoSProfile = None
    ReliabilityPolicy = None
    DurabilityPolicy = None
    HistoryPolicy = None
    Image = None
    LaserScan = None
    String = object
    Bool = object


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
    def __init__(self) -> None:
        self.follow_enabled = False
        self.assistant_enabled = False
        self.server_url = os.getenv("BUDDYBOT_AI_URL", "http://127.0.0.1:8000")
        self.last_command = "idle"
        self.ros2_connected = False

        self._node = None
        self._spin_thread = None
        self._manual_pub = None
        self._follow_pub = None
        self._waypoint_goal_pub = None
        self._waypoint_save_pub = None
        self._nav_cancel_pub = None
        self._map_sub = None
        self._scan_sub = None
        self._executor = None
        self._spin_error: Optional[str] = None
        self._last_scan_error: Optional[str] = None
        self._last_map_error: Optional[str] = None
        self._cv_bridge = CvBridge() if ROS2_AVAILABLE and CvBridge is not None else None

        self._lock = threading.Lock()
        self._latest_pose: Optional[Dict[str, float]] = None
        self._latest_map: Optional[Dict[str, Any]] = None
        self._latest_scan_map: Optional[Dict[str, Any]] = None
        self._latest_scan_stamp: Optional[float] = None
        self._scan_frames_received = 0
        self._latest_camera_jpeg: Optional[bytes] = None
        self._latest_camera_stamp: Optional[float] = None
        self._latest_pico_status: Optional[Dict[str, Any]] = None
        self._system_status = "idle"
        self._navigation_status = "idle"
        self._manual_active = False
        self._manual_linear_x = 0.0
        self._manual_linear_y = 0.0
        self._manual_angular_z = 0.0
        self._last_cli_scan_attempt = 0.0

        self._init_ros()

    def _init_ros(self) -> None:
        if not ROS2_AVAILABLE:
            return
        try:
            if not rclpy.ok():
                rclpy.init(args=None)

            self._node = Node("buddybot_local_panel")
            self._manual_pub = self._node.create_publisher(Twist, "/cmd_vel_manual", 10)
            self._follow_pub = self._node.create_publisher(Bool, "/follow/enabled", 10)
            self._waypoint_goal_pub = self._node.create_publisher(String, "/nav/waypoint_goal", 10)
            self._waypoint_save_pub = self._node.create_publisher(String, "/nav/waypoint_save", 10)
            self._nav_cancel_pub = self._node.create_publisher(String, "/nav/cancel", 10)
            self._node.create_timer(0.1, self._manual_publish_timer)

            map_qos = 10
            if QoSProfile is not None:
                try:
                    # OccupancyGrid from slam_toolbox is published as transient local.
                    map_qos = QoSProfile(
                        reliability=ReliabilityPolicy.RELIABLE,
                        durability=DurabilityPolicy.TRANSIENT_LOCAL,
                        history=HistoryPolicy.KEEP_LAST,
                        depth=1,
                    )
                except Exception:
                    map_qos = 10
            self._map_sub = self._node.create_subscription(OccupancyGrid, "/map", self._map_callback, map_qos)
            self._node.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self._amcl_pose_callback, 10)
            self._node.create_subscription(Odometry, "/odom", self._odom_callback, 10)
            self._node.create_subscription(String, "/system/command_status", self._status_callback, 10)
            self._node.create_subscription(String, "/nav/navigation_status", self._navigation_status_callback, 10)
            if LaserScan is not None:
                scan_qos = 10
                if QoSProfile is not None:
                    try:
                        # Prefer a reliable scan subscription because the Pi LiDAR driver
                        # in this stack publishes reliably.
                        scan_qos = QoSProfile(
                            reliability=ReliabilityPolicy.RELIABLE,
                            durability=DurabilityPolicy.VOLATILE,
                            history=HistoryPolicy.KEEP_LAST,
                            depth=10,
                        )
                    except Exception:
                        scan_qos = 10
                self._scan_sub = self._node.create_subscription(LaserScan, "/scan", self._scan_callback, scan_qos)
            if Status is not None:
                self._node.create_subscription(Status, "/buddybot/pico_status", self._pico_status_callback, 10)
            if Image is not None and self._cv_bridge is not None and QoSProfile is not None:
                image_qos = QoSProfile(
                    reliability=ReliabilityPolicy.BEST_EFFORT,
                    durability=DurabilityPolicy.VOLATILE,
                    history=HistoryPolicy.KEEP_LAST,
                    depth=1,
                )
                self._node.create_subscription(Image, "/camera/image_raw", self._camera_callback, image_qos)

            if SingleThreadedExecutor is not None:
                self._executor = SingleThreadedExecutor()
                self._executor.add_node(self._node)
            self._spin_thread = threading.Thread(target=self._spin_loop, daemon=True)
            self._spin_thread.start()
            self.ros2_connected = True
        except Exception:
            self.ros2_connected = False

    def _spin_loop(self) -> None:
        if self._node is None:
            return
        try:
            while rclpy.ok():
                if self._executor is not None:
                    self._executor.spin_once(timeout_sec=0.2)
                else:
                    rclpy.spin_once(self._node, timeout_sec=0.2)
        except Exception as exc:
            self._spin_error = repr(exc)

    def _status_callback(self, msg: String) -> None:
        self._system_status = msg.data

    def _navigation_status_callback(self, msg: String) -> None:
        self._navigation_status = msg.data

    def _pico_status_callback(self, msg: Status) -> None:
        with self._lock:
            self._latest_pico_status = {
                "battery_voltage": round(float(msg.battery_voltage), 2),
                "emergency_stop": bool(msg.emergency_stop),
                "mode": msg.mode,
                "stamp": time.time(),
            }

    def _map_callback(self, msg: OccupancyGrid) -> None:
        try:
            with self._lock:
                self._latest_map = self._downsample_occupancy_grid(msg, max_width=220, max_height=220)
                self._last_map_error = None
        except Exception as exc:
            self._last_map_error = repr(exc)

    def _scan_callback(self, msg: LaserScan) -> None:
        try:
            with self._lock:
                pose = dict(self._latest_pose) if self._latest_pose is not None else None
            scan_map = self._build_scan_map(msg, pose)
            with self._lock:
                self._latest_scan_map = scan_map
                self._latest_scan_stamp = time.time()
                self._scan_frames_received += 1
                self._last_scan_error = None
        except Exception as exc:
            self._last_scan_error = repr(exc)
            return

    def _camera_callback(self, msg: Image) -> None:
        if self._cv_bridge is None or cv2 is None:
            return
        try:
            frame = self._cv_bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            success, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 72])
            if not success:
                return
            with self._lock:
                self._latest_camera_jpeg = encoded.tobytes()
                self._latest_camera_stamp = time.time()
        except Exception:
            return

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

    def _build_scan_map(
        self,
        msg: LaserScan,
        pose: Optional[Dict[str, float]],
        size_m: float = 8.0,
        resolution: float = 0.05,
    ) -> Dict[str, Any]:
        width = max(1, int(size_m / resolution))
        height = width
        half = size_m / 2.0
        base_x = float(pose["x"]) if pose is not None else 0.0
        base_y = float(pose["y"]) if pose is not None else 0.0
        theta = float(pose["theta"]) if pose is not None else 0.0
        origin_x = base_x - half
        origin_y = base_y - half
        cells = [-1] * (width * height)
        robot_cx = width // 2
        robot_cy = height // 2

        def set_cell(cx: int, cy: int, value: int) -> None:
            if 0 <= cx < width and 0 <= cy < height:
                idx = cy * width + cx
                cells[idx] = max(cells[idx], value)

        def world_to_grid(x: float, y: float) -> tuple[int, int]:
            return int((x - origin_x) / resolution), int((y - origin_y) / resolution)

        def mark_ray(end_x: int, end_y: int, occupied: bool) -> None:
            x0, y0 = robot_cx, robot_cy
            x1, y1 = end_x, end_y
            dx = abs(x1 - x0)
            sx = 1 if x0 < x1 else -1
            dy = -abs(y1 - y0)
            sy = 1 if y0 < y1 else -1
            err = dx + dy
            x, y = x0, y0
            while True:
                if (x, y) != (x1, y1):
                    set_cell(x, y, 0)
                if x == x1 and y == y1:
                    break
                e2 = 2 * err
                if e2 >= dy:
                    err += dy
                    x += sx
                if e2 <= dx:
                    err += dx
                    y += sy
            if occupied:
                set_cell(x1, y1, 100)

        angle = float(msg.angle_min)
        range_min = float(msg.range_min)
        range_max = float(msg.range_max)
        for raw_range in msg.ranges:
            distance = float(raw_range)
            is_valid = math.isfinite(distance) and range_min <= distance <= range_max
            clipped_distance = min(distance, half) if is_valid else half
            heading = theta + angle
            end_x = base_x + math.cos(heading) * clipped_distance
            end_y = base_y + math.sin(heading) * clipped_distance
            gx, gy = world_to_grid(end_x, end_y)
            mark_ray(gx, gy, is_valid and distance <= half)
            angle += float(msg.angle_increment)

        set_cell(robot_cx, robot_cy, 35)
        return {
            "source": "scan_local",
            "width": width,
            "height": height,
            "resolution": resolution,
            "origin": {"x": origin_x, "y": origin_y},
            "cells": cells,
        }

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

    def _poll_scan_from_cli(self, min_interval_sec: float = 2.0) -> bool:
        now = time.time()
        if (now - self._last_cli_scan_attempt) < min_interval_sec:
            return self._latest_scan_map is not None
        self._last_cli_scan_attempt = now
        try:
            result = subprocess.run(
                [
                    "timeout",
                    "3s",
                    "ros2",
                    "topic",
                    "echo",
                    "--qos-reliability",
                    "reliable",
                    "--once",
                    "/scan",
                ],
                check=False,
                capture_output=True,
                text=True,
                env=os.environ.copy(),
            )
            if result.returncode != 0 or not result.stdout.strip():
                return False
            data = yaml.safe_load(result.stdout)
            if not isinstance(data, dict):
                return False
            ranges: List[float] = []
            for item in data.get("ranges", []):
                try:
                    ranges.append(float(item))
                except (TypeError, ValueError):
                    continue
            if not ranges:
                return False
            scan_msg = SimpleNamespace(
                angle_min=float(data["angle_min"]),
                angle_increment=float(data["angle_increment"]),
                range_min=float(data["range_min"]),
                range_max=float(data["range_max"]),
                ranges=ranges,
            )
            with self._lock:
                pose = dict(self._latest_pose) if self._latest_pose is not None else None
            scan_map = self._build_scan_map(scan_msg, pose)
            with self._lock:
                self._latest_scan_map = scan_map
                self._latest_scan_stamp = now
                self._last_scan_error = None
            return True
        except Exception as exc:
            self._last_scan_error = repr(exc)
            return False

    def status(self) -> Dict[str, Any]:
        pose = self.current_pose()
        return {
            "mode": "assistant" if self.assistant_enabled else "standalone",
            "follow_enabled": self.follow_enabled,
            "navigation_status": self._navigation_status,
            "ros2_connected": self.ros2_connected,
            "server_url": self.server_url,
            "server_connected": self.check_server(),
            "last_command": self.last_command,
            "system_status": self._system_status,
            "map_available": self.map_available(),
            "pose_available": pose is not None,
            "pose": pose,
            "camera_available": self.camera_available(),
            "camera_age_sec": self.camera_age_sec(),
            "scan_available": self.scan_available(),
            "scan_age_sec": self.scan_age_sec(),
            "scan_frames_received": self.scan_frames_received(),
            "spin_error": self._spin_error,
            "spin_thread_alive": bool(self._spin_thread and self._spin_thread.is_alive()),
            "last_scan_error": self._last_scan_error,
            "last_map_error": self._last_map_error,
            "pico_connected": self.pico_connected(),
            "pico_status": self.pico_status(),
            "manual_active": self.manual_active(),
        }

    def current_pose(self) -> Optional[Dict[str, float]]:
        with self._lock:
            return dict(self._latest_pose) if self._latest_pose is not None else None

    def map_available(self) -> bool:
        with self._lock:
            return self._latest_map is not None or self._latest_scan_map is not None

    def camera_available(self) -> bool:
        with self._lock:
            return self._latest_camera_jpeg is not None

    def camera_age_sec(self) -> Optional[float]:
        with self._lock:
            if self._latest_camera_stamp is None:
                return None
            return round(max(0.0, time.time() - self._latest_camera_stamp), 2)

    def scan_available(self) -> bool:
        with self._lock:
            return self._latest_scan_map is not None

    def scan_age_sec(self) -> Optional[float]:
        with self._lock:
            if self._latest_scan_stamp is None:
                return None
            return round(max(0.0, time.time() - self._latest_scan_stamp), 2)

    def scan_frames_received(self) -> int:
        with self._lock:
            return int(self._scan_frames_received)

    def get_camera_frame(self) -> Optional[bytes]:
        with self._lock:
            return self._latest_camera_jpeg

    def pico_connected(self) -> bool:
        with self._lock:
            if self._latest_pico_status is None:
                return False
            return (time.time() - float(self._latest_pico_status.get("stamp", 0.0))) < 2.5

    def pico_status(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if self._latest_pico_status is None:
                return None
            status = dict(self._latest_pico_status)
        status["age_sec"] = round(max(0.0, time.time() - float(status.get("stamp", 0.0))), 2)
        status.pop("stamp", None)
        return status

    def manual_active(self) -> bool:
        with self._lock:
            return self._manual_active

    def _publish_follow_state(self, enabled: bool) -> None:
        if not self.ros2_connected or self._follow_pub is None:
            return
        msg = Bool()
        msg.data = bool(enabled)
        self._follow_pub.publish(msg)

    def _clear_manual_motion(self, publish_zero: bool = True) -> None:
        with self._lock:
            self._manual_active = False
            self._manual_linear_x = 0.0
            self._manual_linear_y = 0.0
            self._manual_angular_z = 0.0
        if publish_zero and self.ros2_connected and self._manual_pub is not None:
            self._manual_pub.publish(Twist())

    def cancel_navigation(self) -> None:
        if not self.ros2_connected or self._nav_cancel_pub is None:
            return
        msg = String()
        msg.data = "cancel"
        self._nav_cancel_pub.publish(msg)

    def set_follow_enabled(self, enabled: bool, *, update_last_command: bool = True) -> None:
        self.follow_enabled = bool(enabled)
        if self.follow_enabled:
            self._clear_manual_motion()
            self.cancel_navigation()
        if update_last_command:
            self.last_command = "follow_on" if self.follow_enabled else "follow_off"
        self._publish_follow_state(self.follow_enabled)

    def _manual_publish_timer(self) -> None:
        if not self.ros2_connected or self._manual_pub is None:
            return
        with self._lock:
            active = self._manual_active
            linear_x = self._manual_linear_x
            linear_y = self._manual_linear_y
            angular_z = self._manual_angular_z
        twist = Twist()
        if active:
            twist.linear.x = linear_x
            twist.linear.y = linear_y
            twist.angular.z = angular_z
        self._manual_pub.publish(twist)

    def get_map_payload(self) -> Dict[str, Any]:
        if self._latest_map is None and self._latest_scan_map is None:
            self._poll_scan_from_cli()
        with self._lock:
            if self._latest_map is not None:
                payload = dict(self._latest_map)
            elif self._latest_scan_map is not None:
                payload = dict(self._latest_scan_map)
            else:
                payload = self._build_synthetic_map()
        payload["pose"] = self.current_pose()
        return payload

    def set_assistant(self, enabled: bool, server_url: str) -> Dict[str, Any]:
        self.assistant_enabled = enabled
        self.server_url = server_url.rstrip("/")
        self.last_command = f"assistant:{'on' if enabled else 'off'}"
        return self.status()

    def check_server(self) -> bool:
        try:
            response = requests.get(f"{self.server_url}/health", timeout=1.0)
            return response.ok
        except requests.RequestException:
            return False

    def handle_chat(self, message: str) -> str:
        if self.assistant_enabled and self.check_server():
            try:
                response = requests.post(
                    f"{self.server_url}/chat",
                    json={"message": message},
                    timeout=15,
                )
                response.raise_for_status()
                return response.json().get("response", "No response received.")
            except requests.RequestException:
                pass
        return self._handle_local_command(message)

    def _handle_local_command(self, message: str) -> str:
        text = message.lower().strip()
        wake_words = ("버디봇", "버디봇아", "버디", "buddybot", "buddy")

        if text in wake_words:
            return "네, 부르셨어요?"

        for wake_word in wake_words:
            if text.startswith(f"{wake_word} "):
                text = text[len(wake_word):].strip()
                break
            if text.startswith(f"{wake_word},"):
                text = text[len(wake_word) + 1:].strip()
                break

        if not text:
            return "네, 말씀하세요."

        if any(keyword in text for keyword in ("stop", "halt", "brake", "정지", "멈춰", "스톱")):
            self.manual_command("stop", 0.0)
            return "Standalone mode에서 로봇을 정지했습니다."
        if any(keyword in text for keyword in ("forward", "go ahead", "앞으로", "전진")):
            self.manual_command("forward", 0.35)
            return "Standalone mode에서 앞으로 이동합니다."
        if any(keyword in text for keyword in ("backward", "reverse", "back", "뒤로", "후진")):
            self.manual_command("backward", 0.35)
            return "Standalone mode에서 뒤로 이동합니다."
        if any(keyword in text for keyword in ("strafe left", "slide left", "왼쪽 이동", "왼쪽으로")):
            self.manual_command("strafe_left", 0.3)
            return "Standalone mode에서 왼쪽으로 이동합니다."
        if any(keyword in text for keyword in ("strafe right", "slide right", "오른쪽 이동", "오른쪽으로")):
            self.manual_command("strafe_right", 0.3)
            return "Standalone mode에서 오른쪽으로 이동합니다."
        if any(keyword in text for keyword in ("turn left", "rotate left", "좌회전", "왼쪽 회전")):
            self.manual_command("rotate_left", 0.45)
            return "Standalone mode에서 좌회전합니다."
        if any(keyword in text for keyword in ("turn right", "rotate right", "우회전", "오른쪽 회전")):
            self.manual_command("rotate_right", 0.45)
            return "Standalone mode에서 우회전합니다."
        if any(keyword in text for keyword in ("follow stop", "unfollow", "추종 중지", "따라오지마", "추종 꺼")):
            self.set_follow_enabled(False)
            return "사용자 추종을 중지했습니다."
        if any(keyword in text for keyword in ("follow", "track user", "따라와", "추종 시작", "추종 켜")):
            self.set_follow_enabled(True)
            return "사용자 추종을 시작했습니다."
        if any(keyword in text for keyword in ("status", "state", "상태", "지금 상태")):
            pose = self.current_pose()
            if pose is None:
                return "버디봇은 온라인 상태입니다. 센서는 동작 중이지만 현재 위치는 아직 잡히지 않았습니다."
            return (
                f"버디봇은 온라인 상태입니다. 위치는 x={pose['x']}, y={pose['y']}, theta={pose['theta']}이고, "
                f"카메라는 {'켜짐' if self.camera_available() else '대기'}, 맵은 {'준비됨' if self.map_available() else '대기'} 상태입니다."
            )
        if "kitchen" in text or "주방" in text or "부엌" in text:
            self.go_waypoint("kitchen")
            return "주방으로 이동 요청을 보냈습니다."
        if "living room" in text or "거실" in text:
            self.go_waypoint("living_room_center")
            return "거실로 이동 요청을 보냈습니다."
        if "charge" in text or "충전" in text or "도킹" in text:
            self.go_waypoint("charging_station")
            return "충전 스테이션으로 이동 요청을 보냈습니다."
        return "Standalone BuddyBot mode입니다. 버디봇이라고 부른 뒤 전진, 좌회전, 왼쪽 이동, 정지, 추종, 상태, 주방 같은 명령을 써보세요."

    def manual_command(self, direction: str, speed: float) -> None:
        self.last_command = f"manual:{direction}"
        self.follow_enabled = False
        self._publish_follow_state(False)
        self.cancel_navigation()
        linear_x = 0.0
        linear_y = 0.0
        angular_z = 0.0

        if direction == "forward":
            linear_x = speed
        elif direction == "backward":
            linear_x = -speed
        elif direction == "strafe_left":
            linear_y = speed
        elif direction == "strafe_right":
            linear_y = -speed
        elif direction == "rotate_left":
            angular_z = speed
        elif direction == "rotate_right":
            angular_z = -speed

        if direction == "stop":
            self._clear_manual_motion()
            return

        if not self.ros2_connected or self._manual_pub is None:
            return

        with self._lock:
            self._manual_active = True
            self._manual_linear_x = linear_x
            self._manual_linear_y = linear_y
            self._manual_angular_z = angular_z

    def go_waypoint(self, name: str) -> None:
        self.last_command = f"nav:{name}"
        self.set_follow_enabled(False, update_last_command=False)
        self._clear_manual_motion()
        if self.ros2_connected and self._waypoint_goal_pub is not None:
            msg = String()
            msg.data = name
            self._waypoint_goal_pub.publish(msg)

    def save_waypoint(
        self,
        name: str,
        x: Optional[float],
        y: Optional[float],
        theta: float,
        description: str,
    ) -> Dict[str, Any]:
        if x is None or y is None:
            pose = self.current_pose()
            if pose is None:
                raise ValueError("Current pose is not available.")
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
                {
                    "name": name,
                    "x": float(x),
                    "y": float(y),
                    "theta": float(theta),
                    "description": description or name,
                },
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


@app.get("/api/camera.jpg")
def api_camera():
    frame = bridge.get_camera_frame()
    if frame is None:
        raise HTTPException(status_code=404, detail="Camera frame not available yet.")
    return Response(content=frame, media_type="image/jpeg")


@app.post("/api/assistant")
def api_assistant(settings: AssistantSettings):
    return bridge.set_assistant(settings.enabled, settings.server_url)


@app.post("/api/chat")
def api_chat(request: ChatRequest):
    return {"response": bridge.handle_chat(request.message)}


@app.post("/api/manual")
def api_manual(request: Dict[str, Any]):
    bridge.manual_command(
        request.get("direction", "stop"),
        float(request.get("speed", 0.35)),
    )
    return bridge.status()


@app.post("/api/follow")
def api_follow(request: Dict[str, Any]):
    bridge.set_follow_enabled(bool(request.get("enabled", False)))
    return bridge.status()


@app.get("/api/waypoints")
def api_waypoints():
    return {"items": bridge.list_waypoints()}


@app.post("/api/waypoints")
def api_save_waypoint(request: WaypointSaveRequest):
    waypoint = bridge.save_waypoint(
        request.name,
        request.x,
        request.y,
        request.theta,
        request.description,
    )
    return {"saved": True, "waypoint": waypoint, "items": bridge.list_waypoints()}


@app.post("/api/waypoints/current")
def api_save_current_waypoint(request: CurrentPoseWaypointRequest):
    waypoint = bridge.save_waypoint(request.name, None, None, 0.0, request.description)
    return {"saved": True, "waypoint": waypoint, "items": bridge.list_waypoints()}


@app.post("/api/go")
def api_go(request: WaypointGoRequest):
    bridge.go_waypoint(request.name)
    return {"success": True, "message": f"Sent navigation request to {request.name}."}


def main() -> None:
    host = os.getenv("BUDDYBOT_PANEL_HOST", "0.0.0.0")
    port = int(os.getenv("BUDDYBOT_PANEL_PORT", "8090"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
