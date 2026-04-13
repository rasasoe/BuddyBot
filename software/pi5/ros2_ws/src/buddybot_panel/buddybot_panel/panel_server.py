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
    from ament_index_python.packages import get_package_share_directory
except Exception:
    get_package_share_directory = None

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
    from std_msgs.msg import Bool, Float32MultiArray, String

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
    Float32MultiArray = object


PACKAGE_DIR = Path(__file__).resolve().parent


def _first_existing_path(candidates: List[Path]) -> Path:
    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate.resolve()
        except OSError:
            continue
    return candidates[0].resolve()


def _resolve_static_dir() -> Path:
    candidates: List[Path] = []

    env_static = os.getenv("BUDDYBOT_PANEL_STATIC_DIR", "").strip()
    if env_static:
        candidates.append(Path(env_static))

    candidates.append(PACKAGE_DIR / "static")
    candidates.append(Path.cwd() / "software" / "pi5" / "ros2_ws" / "src" / "buddybot_panel" / "buddybot_panel" / "static")

    if get_package_share_directory is not None:
        try:
            candidates.append(Path(get_package_share_directory("buddybot_panel")) / "static")
        except Exception:
            pass

    return _first_existing_path(candidates)


def _resolve_waypoint_file() -> Path:
    candidates: List[Path] = []

    env_waypoint = os.getenv("BUDDYBOT_WAYPOINT_FILE", "").strip()
    if env_waypoint:
        candidates.append(Path(env_waypoint))

    candidates.append(Path.cwd() / "software" / "pi5" / "ros2_ws" / "src" / "buddybot_nav" / "config" / "waypoints.yaml")
    candidates.append((PACKAGE_DIR.parent.parent / "buddybot_nav" / "config" / "waypoints.yaml").resolve())

    if get_package_share_directory is not None:
        try:
            candidates.append(Path(get_package_share_directory("buddybot_nav")) / "config" / "waypoints.yaml")
        except Exception:
            pass

    return _first_existing_path(candidates)


def _derive_panel_build() -> str:
    explicit = os.getenv("BUDDYBOT_PANEL_BUILD", "").strip()
    if explicit:
        return explicit

    stamp_paths = [PACKAGE_DIR / "panel_server.py", _resolve_static_dir() / "index.html"]
    newest = 0
    for path in stamp_paths:
        try:
            newest = max(newest, int(path.stat().st_mtime))
        except OSError:
            continue
    return f"panel-{newest}" if newest else "panel-unknown"


STATIC_DIR = _resolve_static_dir()
WAYPOINT_FILE = _resolve_waypoint_file()
PANEL_BUILD = _derive_panel_build()
INDEX_FILE = STATIC_DIR / "index.html"


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


class WaypointDeleteRequest(BaseModel):
    name: str


class DestinationSaveRequest(BaseModel):
    name: str
    sequence: List[str]
    description: str = ""


class DestinationGoRequest(BaseModel):
    name: str


class RouteRunRequest(BaseModel):
    name: str = "route_now"
    sequence: List[str]


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
        self._waypoint_delete_pub = None
        self._waypoint_clear_pub = None
        self._destination_goal_pub = None
        self._destination_save_pub = None
        self._destination_delete_pub = None
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
        self._latest_scan_summary: Optional[Dict[str, float]] = None
        self._scan_frames_received = 0
        self._latest_camera_jpeg: Optional[bytes] = None
        self._latest_camera_stamp: Optional[float] = None
        self._latest_detector_status: Optional[Dict[str, Any]] = None
        self._latest_pico_status: Optional[Dict[str, Any]] = None
        self._latest_person_bbox: Optional[Dict[str, float]] = None
        self._latest_person_stamp: Optional[float] = None
        self._person_frames_received = 0
        self._safety_active = False
        self._safety_status = "active:False,sources:"
        self._system_status = "idle"
        self._navigation_status = "idle"
        self._manual_active = False
        self._manual_linear_x = 0.0
        self._manual_linear_y = 0.0
        self._manual_angular_z = 0.0
        self._last_cli_scan_attempt = 0.0
        self._mini_map: Optional[Dict[str, Any]] = None
        self._mini_map_active = False
        self._mini_map_completed = False
        self._mini_map_started_at: Optional[float] = None
        self._mini_map_completed_at: Optional[float] = None
        self._mini_map_frames = 0
        self._mini_map_distance_m = 0.0
        self._mini_map_last_pose: Optional[Dict[str, float]] = None
        self._mini_map_completion_goal_cells = 7500
        self._mini_map_min_duration_sec = 18.0
        self._mini_map_target_duration_sec = 36.0
        self._mini_map_known_cells = 0
        self._mini_map_grid_dim = 200          # 20 m / 0.1 m per cell
        self._mini_map_grid_resolution = 0.10  # metres per cell
        self._mini_map_grid_size_m = 20.0
        self._mini_map_cells: Optional[List[int]] = None
        self._mini_map_origin_x = 0.0
        self._mini_map_origin_y = 0.0
        # Autonomous exploration state for minimap coverage.
        self._explore_phase = "forward"      # "forward" | "turning" | "backing" | "strafing"
        self._explore_turn_direction = 1.0
        self._explore_turn_remaining = 0.0
        self._explore_last_step = 0.0
        self._explore_last_sweep_at = 0.0
        # Server connectivity cache
        self._server_connected = False
        self._server_check_at = 0.0

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
            self._waypoint_delete_pub = self._node.create_publisher(String, "/nav/waypoint_delete", 10)
            self._waypoint_clear_pub = self._node.create_publisher(String, "/nav/waypoint_clear", 10)
            self._destination_goal_pub = self._node.create_publisher(String, "/nav/destination_goal", 10)
            self._destination_save_pub = self._node.create_publisher(String, "/nav/destination_save", 10)
            self._destination_delete_pub = self._node.create_publisher(String, "/nav/destination_delete", 10)
            self._nav_cancel_pub = self._node.create_publisher(String, "/nav/cancel", 10)
            self._node.create_timer(0.1, self._manual_publish_timer)
            self._node.create_timer(0.2, self._mini_map_timer)

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
            self._node.create_subscription(String, "/system/safety_status", self._safety_status_callback, 10)
            self._node.create_subscription(Bool, "/system/safety_active", self._safety_active_callback, 10)
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
            self._node.create_subscription(String, "/vision/detector_status", self._detector_status_callback, 10)
            if Float32MultiArray is not None:
                self._node.create_subscription(Float32MultiArray, "/vision/person_bbox", self._person_bbox_callback, 10)

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

    def _safety_status_callback(self, msg: String) -> None:
        self._safety_status = msg.data

    def _safety_active_callback(self, msg: Bool) -> None:
        self._safety_active = bool(msg.data)

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
            scan_summary = self._summarize_scan(msg)
            with self._lock:
                self._latest_scan_map = scan_map
                self._latest_scan_stamp = time.time()
                self._latest_scan_summary = scan_summary
                self._scan_frames_received += 1
                self._last_scan_error = None
            self._accumulate_mini_map_scan(msg, pose)
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

    def _detector_status_callback(self, msg: String) -> None:
        payload: Dict[str, Any]
        try:
            parsed = json.loads(msg.data)
            if isinstance(parsed, dict):
                payload = dict(parsed)
            else:
                payload = {"details": str(parsed)}
        except Exception:
            payload = {"details": msg.data}

        payload.setdefault("backend", "unknown")
        payload.setdefault("ready", False)
        payload.setdefault("reason", "unparsed_status")
        payload["stamp"] = time.time()

        with self._lock:
            self._latest_detector_status = payload

    def _person_bbox_callback(self, msg: Float32MultiArray) -> None:
        try:
            if len(msg.data) < 5:
                return
            x, y, width, height, confidence = msg.data[:5]
            with self._lock:
                self._latest_person_bbox = {
                    "x": round(float(x), 2),
                    "y": round(float(y), 2),
                    "width": round(float(width), 2),
                    "height": round(float(height), 2),
                    "confidence": round(float(confidence), 3),
                }
                self._latest_person_stamp = time.time()
                self._person_frames_received += 1
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

    def _summarize_scan(self, msg: LaserScan) -> Dict[str, float]:
        def sector_min(start_ratio: float, end_ratio: float) -> float:
            count = len(msg.ranges)
            if count <= 0:
                return float("inf")
            start = max(0, min(count, int(count * start_ratio)))
            end = max(start + 1, min(count, int(count * end_ratio)))
            values = []
            for raw_range in msg.ranges[start:end]:
                distance = float(raw_range)
                if math.isfinite(distance) and msg.range_min <= distance <= msg.range_max:
                    values.append(distance)
            return min(values) if values else float("inf")

        return {
            "front_min": round(min(sector_min(0.0, 0.08), sector_min(0.92, 1.0)), 3),
            "front_left_min": round(sector_min(0.08, 0.20), 3),
            "front_right_min": round(sector_min(0.80, 0.92), 3),
            "left_min": round(sector_min(0.20, 0.38), 3),
            "right_min": round(sector_min(0.62, 0.80), 3),
            "rear_min": round(sector_min(0.42, 0.58), 3),
            "valid_points": float(
                sum(
                    1
                    for raw_range in msg.ranges
                    if math.isfinite(float(raw_range)) and msg.range_min <= float(raw_range) <= msg.range_max
                )
            ),
        }

    def _new_mini_map(self, anchor_pose: Optional[Dict[str, float]], size_m: float = 14.0, resolution: float = 0.05) -> Dict[str, Any]:
        width = max(1, int(size_m / resolution))
        height = width
        anchor_x = float(anchor_pose["x"]) if anchor_pose is not None else 0.0
        anchor_y = float(anchor_pose["y"]) if anchor_pose is not None else 0.0
        return {
            "source": "mini_map",
            "width": width,
            "height": height,
            "resolution": resolution,
            "origin": {
                "x": anchor_x - (size_m / 2.0),
                "y": anchor_y - (size_m / 2.0),
            },
            "cells": [-1] * (width * height),
        }

    def _grid_index(self, width: int, height: int, cx: int, cy: int) -> Optional[int]:
        if not (0 <= cx < width and 0 <= cy < height):
            return None
        return cy * width + cx

    def _mini_map_world_to_grid(self, x: float, y: float, mini_map: Dict[str, Any]) -> tuple[int, int]:
        origin = mini_map["origin"]
        resolution = float(mini_map["resolution"])
        return (
            int((x - float(origin["x"])) / resolution),
            int((y - float(origin["y"])) / resolution),
        )

    def _trace_ray(self, mini_map: Dict[str, Any], start: tuple[int, int], end: tuple[int, int], occupied: bool) -> None:
        width = int(mini_map["width"])
        height = int(mini_map["height"])
        cells = mini_map["cells"]
        x0, y0 = start
        x1, y1 = end
        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        x, y = x0, y0
        while True:
            if (x, y) != (x1, y1):
                idx = self._grid_index(width, height, x, y)
                if idx is not None and cells[idx] < 0:
                    cells[idx] = 0
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
            idx = self._grid_index(width, height, x1, y1)
            if idx is not None:
                cells[idx] = 100

    def _accumulate_mini_map_scan(self, msg: LaserScan, pose: Optional[Dict[str, float]]) -> None:
        with self._lock:
            mini_map = self._mini_map
            active = self._mini_map_active

        if mini_map is None:
            return

        base_pose = pose or self.current_pose() or {"x": 0.0, "y": 0.0, "theta": 0.0}
        base_x = float(base_pose["x"])
        base_y = float(base_pose["y"])
        theta = float(base_pose["theta"])
        start = self._mini_map_world_to_grid(base_x, base_y, mini_map)
        half_span = (float(mini_map["width"]) * float(mini_map["resolution"])) / 2.0

        angle = float(msg.angle_min)
        range_min = float(msg.range_min)
        range_max = float(msg.range_max)
        for raw_range in msg.ranges:
            distance = float(raw_range)
            is_valid = math.isfinite(distance) and range_min <= distance <= range_max
            clipped_distance = min(distance, half_span) if is_valid else half_span
            heading = theta + angle
            end_x = base_x + math.cos(heading) * clipped_distance
            end_y = base_y + math.sin(heading) * clipped_distance
            end = self._mini_map_world_to_grid(end_x, end_y, mini_map)
            self._trace_ray(mini_map, start, end, occupied=is_valid and distance <= half_span)
            angle += float(msg.angle_increment)

        now = time.time()
        with self._lock:
            self._mini_map = mini_map
            self._mini_map_frames += 1
            last_pose = self._mini_map_last_pose
            if last_pose is not None:
                self._mini_map_distance_m += math.hypot(base_x - float(last_pose["x"]), base_y - float(last_pose["y"]))
            self._mini_map_last_pose = {"x": base_x, "y": base_y, "theta": theta}
            if active and self._mini_map_should_complete(now):
                self._mini_map_active = False
                self._mini_map_completed = True
                self._mini_map_completed_at = now
                self._manual_active = False
                self._manual_linear_x = 0.0
                self._manual_linear_y = 0.0
                self._manual_angular_z = 0.0

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
            scan_summary = self._summarize_scan(scan_msg)
            with self._lock:
                self._latest_scan_map = scan_map
                self._latest_scan_stamp = now
                self._latest_scan_summary = scan_summary
                self._last_scan_error = None
            self._accumulate_mini_map_scan(scan_msg, pose)
            return True
        except Exception as exc:
            self._last_scan_error = repr(exc)
            return False

    def status(self) -> Dict[str, Any]:
        pose = self.current_pose()
        return {
            "panel_build": PANEL_BUILD,
            "panel_static_dir": str(STATIC_DIR),
            "waypoint_file": str(WAYPOINT_FILE),
            "mode": "assistant" if self.assistant_enabled else "standalone",
            "follow_enabled": self.follow_enabled,
            "navigation_status": self._navigation_status,
            "ros2_connected": self.ros2_connected,
            "server_url": self.server_url,
            "server_connected": self._cached_server_connected(),
            "last_command": self.last_command,
            "system_status": self._system_status,
            "map_available": self.map_available(),
            "pose_available": pose is not None,
            "pose": pose,
            "camera_available": self.camera_available(),
            "camera_age_sec": self.camera_age_sec(),
            "detector_status": self.detector_status(),
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
            "safety_active": self.safety_active(),
            "safety_status": self.safety_status(),
            "person_detected": self.person_detected(),
            "person_age_sec": self.person_age_sec(),
            "person_bbox": self.person_bbox(),
            "person_frames_received": self.person_frames_received(),
            "sensor_fusion": self.sensor_fusion_summary(),
            "minimap": self.mini_map_status(),
        }

    def current_pose(self) -> Optional[Dict[str, float]]:
        with self._lock:
            return dict(self._latest_pose) if self._latest_pose is not None else None

    def _mini_map_has_data(self, mini_map: Optional[Dict[str, Any]]) -> bool:
        return mini_map is not None and any(int(cell) >= 0 for cell in mini_map.get("cells", []))

    def map_available(self) -> bool:
        with self._lock:
            mini_map_ready = self._mini_map_has_data(self._mini_map)
            return self._latest_map is not None or self._latest_scan_map is not None or mini_map_ready

    def camera_available(self) -> bool:
        with self._lock:
            return self._latest_camera_jpeg is not None and self._latest_camera_stamp is not None and (time.time() - self._latest_camera_stamp) < 3.0

    def camera_age_sec(self) -> Optional[float]:
        with self._lock:
            if self._latest_camera_stamp is None:
                return None
            return round(max(0.0, time.time() - self._latest_camera_stamp), 2)

    def scan_available(self) -> bool:
        needs_probe = False
        with self._lock:
            needs_probe = self._latest_scan_map is None or self._latest_scan_stamp is None or (time.time() - self._latest_scan_stamp) >= 3.0
        if needs_probe:
            self._poll_scan_from_cli(min_interval_sec=3.0)
        with self._lock:
            return self._latest_scan_map is not None and self._latest_scan_stamp is not None and (time.time() - self._latest_scan_stamp) < 3.0

    def scan_age_sec(self) -> Optional[float]:
        with self._lock:
            if self._latest_scan_stamp is None:
                return None
            return round(max(0.0, time.time() - self._latest_scan_stamp), 2)

    def scan_frames_received(self) -> int:
        with self._lock:
            return int(self._scan_frames_received)

    def detector_status(self, stale_after_sec: float = 4.0) -> Dict[str, Any]:
        with self._lock:
            detector = dict(self._latest_detector_status) if self._latest_detector_status is not None else None

        if detector is None:
            return {
                "backend": "waiting",
                "ready": False,
                "live": False,
                "reason": "waiting_for_detector",
                "details": "Detector status topic has not published yet.",
                "age_sec": None,
            }

        stamp = float(detector.pop("stamp", 0.0))
        age_sec = round(max(0.0, time.time() - stamp), 2) if stamp else None
        live = age_sec is not None and age_sec <= stale_after_sec
        detector["age_sec"] = age_sec
        detector["live"] = live
        detector["ready"] = bool(detector.get("ready", False)) and live
        if not live and detector.get("reason") == "model_loaded":
            detector["reason"] = "stale_status"
        return detector

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

    def safety_active(self) -> bool:
        return bool(self._safety_active)

    def safety_status(self) -> str:
        return self._safety_status

    def person_detected(self, stale_after_sec: float = 1.2) -> bool:
        with self._lock:
            if self._latest_person_stamp is None:
                return False
            return (time.time() - self._latest_person_stamp) <= stale_after_sec

    def person_age_sec(self) -> Optional[float]:
        with self._lock:
            if self._latest_person_stamp is None:
                return None
            return round(max(0.0, time.time() - self._latest_person_stamp), 2)

    def person_bbox(self) -> Optional[Dict[str, float]]:
        with self._lock:
            if self._latest_person_bbox is None:
                return None
            return dict(self._latest_person_bbox)

    def person_frames_received(self) -> int:
        with self._lock:
            return int(self._person_frames_received)

    def sensor_fusion_summary(self) -> Dict[str, Any]:
        pose_ready = self.current_pose() is not None
        lidar_live = self.scan_available()
        camera_live = self.camera_available()
        map_live = self.map_available()
        person_live = self.person_detected()
        detector = self.detector_status()
        detector_ready = bool(detector.get("ready", False))
        pico_live = self.pico_connected()
        safety_clear = not self.safety_active()

        blockers: List[str] = []
        if not lidar_live:
            blockers.append("lidar_missing")
        if not camera_live:
            blockers.append("camera_missing")
        if not pose_ready:
            blockers.append("pose_missing")
        if not map_live:
            blockers.append("map_missing")
        if not pico_live:
            blockers.append("pico_missing")
        if not safety_clear:
            blockers.append("safety_latched")

        follow_blockers: List[str] = []
        if not camera_live:
            follow_blockers.append("camera_missing")
        if not detector_ready:
            follow_blockers.append("detector_unavailable")
        if detector_ready and not person_live:
            follow_blockers.append("person_not_detected")
        if not lidar_live:
            follow_blockers.append("lidar_missing")
        if not safety_clear:
            follow_blockers.append("safety_latched")

        nav_blockers: List[str] = []
        if not pose_ready:
            nav_blockers.append("pose_missing")
        if not map_live:
            nav_blockers.append("map_missing")
        if not lidar_live:
            nav_blockers.append("lidar_missing")
        if not safety_clear:
            nav_blockers.append("safety_latched")

        return {
            "camera_lidar_ready": camera_live and lidar_live,
            "vision_ready": camera_live and detector_ready,
            "fusion_ready": camera_live and lidar_live and pose_ready and map_live,
            "follow_ready": not follow_blockers,
            "follow_state": (
                "tracking" if self.follow_enabled and person_live else
                "armed" if self.follow_enabled else
                "idle"
            ),
            "nav_ready": not nav_blockers,
            "operator_ready": not blockers,
            "detector_backend": detector.get("backend", "waiting"),
            "detector_reason": detector.get("reason", "waiting_for_detector"),
            "blockers": blockers,
            "follow_blockers": follow_blockers,
            "nav_blockers": nav_blockers,
        }

    def mini_map_status(self) -> Dict[str, Any]:
        with self._lock:
            mini_map = dict(self._mini_map) if self._mini_map is not None else None
            active = bool(self._mini_map_active)
            completed = bool(self._mini_map_completed)
            started_at = self._mini_map_started_at
            completed_at = self._mini_map_completed_at
            frames = int(self._mini_map_frames)
            distance_m = round(float(self._mini_map_distance_m), 2)
            scan_summary = dict(self._latest_scan_summary) if self._latest_scan_summary is not None else None
            explore_phase = str(self._explore_phase)

        duration_sec = round(max(0.0, time.time() - started_at), 2) if started_at else 0.0
        known_cells = 0
        occupied_cells = 0
        progress = 0.0
        if mini_map is not None:
            cells = mini_map.get("cells", [])
            known_cells = sum(1 for cell in cells if int(cell) >= 0)
            occupied_cells = sum(1 for cell in cells if int(cell) >= 65)
            cell_progress = min(1.0, known_cells / float(self._mini_map_completion_goal_cells))
            time_progress = min(1.0, duration_sec / float(self._mini_map_target_duration_sec))
            progress = round(min(1.0, (cell_progress * 0.75) + (time_progress * 0.25)), 3)

        status = "idle"
        if active:
            status = "building"
        elif completed:
            status = "complete"
        elif mini_map is not None:
            status = "paused"

        effective_front = None
        if scan_summary is not None:
            front_values = [
                float(scan_summary.get("front_min", float("inf"))),
                float(scan_summary.get("front_left_min", float("inf"))),
                float(scan_summary.get("front_right_min", float("inf"))),
            ]
            finite_front = [value for value in front_values if math.isfinite(value)]
            if finite_front:
                effective_front = round(min(finite_front), 2)

        phase_label = {
            "forward": "전진 탐색",
            "turning": "회전 회피",
            "backing": "후진 복구",
            "strafing": "측면 보정",
        }.get(explore_phase, "대기")

        return {
            "active": active,
            "completed": completed,
            "status": status,
            "duration_sec": duration_sec,
            "frames": frames,
            "distance_m": distance_m,
            "known_cells": known_cells,
            "occupied_cells": occupied_cells,
            "progress": progress,
            "progress_percent": int(round(progress * 100)),
            "completed_at": completed_at,
            "scan_summary": scan_summary,
            "map_available": mini_map is not None and known_cells > 0,
            "explore_phase": explore_phase,
            "explore_phase_label": phase_label,
            "front_clearance_m": effective_front,
        }

    def _mini_map_should_complete(self, now: float) -> bool:
        if self._mini_map is None or self._mini_map_started_at is None:
            return False
        elapsed = now - self._mini_map_started_at
        if elapsed < self._mini_map_min_duration_sec or self._mini_map_frames < 45:
            return False
        cells = self._mini_map.get("cells", [])
        known_cells = sum(1 for cell in cells if int(cell) >= 0)
        if known_cells >= self._mini_map_completion_goal_cells:
            return True
        return elapsed >= self._mini_map_target_duration_sec and known_cells >= max(1800, self._mini_map_completion_goal_cells // 3)

    def _set_manual_motion(self, linear_x: float, linear_y: float, angular_z: float) -> None:
        with self._lock:
            self._manual_active = True
            self._manual_linear_x = float(linear_x)
            self._manual_linear_y = float(linear_y)
            self._manual_angular_z = float(angular_z)

    def _set_explore_phase(self, phase: str, duration_sec: float, direction: float, now: Optional[float] = None) -> None:
        started_at = time.time() if now is None else float(now)
        self._explore_phase = phase
        self._explore_turn_direction = 1.0 if direction >= 0.0 else -1.0
        self._explore_turn_remaining = max(0.0, float(duration_sec))
        self._explore_last_step = started_at
        self._explore_last_sweep_at = started_at

    def _mini_map_timer(self) -> None:
        # Always publish follow-enable state so follow_controller stays in sync.
        if self.ros2_connected and self._follow_pub is not None:
            fmsg = Bool()
            fmsg.data = self.follow_enabled
            self._follow_pub.publish(fmsg)

        with self._lock:
            active = bool(self._mini_map_active)
            scan_summary = dict(self._latest_scan_summary) if self._latest_scan_summary is not None else None
            safety_active = bool(self._safety_active)
            scan_stamp = self._latest_scan_stamp

        if not active:
            return

        # Pause exploration on safety latch or stale scan data.
        if safety_active or scan_summary is None or scan_stamp is None or (time.time() - scan_stamp) > 2.0:
            self._clear_manual_motion()
            return

        now = time.time()
        front_min = float(scan_summary.get("front_min", float("inf")))
        front_left_min = float(scan_summary.get("front_left_min", float("inf")))
        front_right_min = float(scan_summary.get("front_right_min", float("inf")))
        left_min = float(scan_summary.get("left_min", float("inf")))
        right_min = float(scan_summary.get("right_min", float("inf")))
        effective_front = min(front_min, front_left_min, front_right_min)
        open_left = min(left_min, front_left_min)
        open_right = min(right_min, front_right_min)
        turn_direction = 1.0 if open_left >= open_right else -1.0
        phase_elapsed = now - self._explore_last_step

        TURN_SPD = 0.56
        FWD_SPD = 0.16
        STRAFE_SPD = 0.11
        BACK_SPD = -0.10
        VERY_CLOSE_FRONT = 0.32
        FRONT_BLOCKED = 0.55
        SIDE_TIGHT = 0.30
        SIDE_NEAR = 0.44
        COVER_PERIOD = 7.0

        if self._explore_phase == "backing":
            if phase_elapsed < self._explore_turn_remaining:
                self._set_manual_motion(BACK_SPD, STRAFE_SPD * 0.35 * self._explore_turn_direction, 0.0)
                return
            self._set_explore_phase("turning", 1.15, turn_direction, now)
            self._set_manual_motion(0.0, 0.0, TURN_SPD * self._explore_turn_direction)
            return

        if self._explore_phase == "turning":
            if phase_elapsed < self._explore_turn_remaining:
                self._set_manual_motion(0.0, 0.0, TURN_SPD * self._explore_turn_direction)
                return
            self._explore_phase = "forward"

        if self._explore_phase == "strafing":
            if phase_elapsed < self._explore_turn_remaining:
                self._set_manual_motion(
                    FWD_SPD * 0.55,
                    STRAFE_SPD * self._explore_turn_direction,
                    0.18 * self._explore_turn_direction,
                )
                return
            self._explore_phase = "forward"

        if effective_front < VERY_CLOSE_FRONT:
            self._set_explore_phase("backing", 0.7, turn_direction, now)
            self._set_manual_motion(BACK_SPD, STRAFE_SPD * 0.3 * self._explore_turn_direction, 0.0)
            return

        if effective_front < FRONT_BLOCKED:
            turn_duration = 1.0 + max(0.0, FRONT_BLOCKED - effective_front) * 1.7
            self._set_explore_phase("turning", min(1.8, turn_duration), turn_direction, now)
            self._set_manual_motion(0.0, 0.0, TURN_SPD * self._explore_turn_direction)
            return

        if left_min < SIDE_TIGHT and right_min > left_min + 0.06:
            self._set_explore_phase("strafing", 0.85, -1.0, now)
            self._set_manual_motion(FWD_SPD * 0.55, -STRAFE_SPD, -0.18)
            return

        if right_min < SIDE_TIGHT and left_min > right_min + 0.06:
            self._set_explore_phase("strafing", 0.85, 1.0, now)
            self._set_manual_motion(FWD_SPD * 0.55, STRAFE_SPD, 0.18)
            return

        if left_min < SIDE_NEAR and right_min > left_min + 0.05:
            self._set_manual_motion(FWD_SPD * 0.78, -STRAFE_SPD * 0.45, -0.12)
            return

        if right_min < SIDE_NEAR and left_min > right_min + 0.05:
            self._set_manual_motion(FWD_SPD * 0.78, STRAFE_SPD * 0.45, 0.12)
            return

        if now - self._explore_last_sweep_at >= COVER_PERIOD:
            sweep_direction = 1.0 if (self._mini_map_frames // 12) % 2 == 0 else -1.0
            if min(open_left, open_right) < SIDE_NEAR:
                sweep_direction = turn_direction
            self._set_explore_phase("turning", 0.9 if effective_front > 0.9 else 0.65, sweep_direction, now)
            self._set_manual_motion(0.0, 0.0, TURN_SPD * self._explore_turn_direction)
            return

        self._set_manual_motion(FWD_SPD, 0.0, 0.0)

    def start_mini_map(self) -> Dict[str, Any]:
        anchor_pose = self.current_pose() or {"x": 0.0, "y": 0.0, "theta": 0.0, "source": "panel"}
        self.set_follow_enabled(False, update_last_command=False)
        self.cancel_navigation()
        self._clear_manual_motion()
        with self._lock:
            self._mini_map = self._new_mini_map(anchor_pose)
            self._mini_map_active = True
            self._mini_map_completed = False
            self._mini_map_started_at = time.time()
            self._mini_map_completed_at = None
            self._mini_map_frames = 0
            self._mini_map_distance_m = 0.0
            self._mini_map_last_pose = {"x": float(anchor_pose["x"]), "y": float(anchor_pose["y"]), "theta": float(anchor_pose["theta"])}
        self.last_command = "minimap:start"
        # Reset exploration state machine so every new session starts clean.
        self._explore_phase = "forward"
        self._explore_turn_direction = 1.0
        self._explore_turn_remaining = 0.0
        self._explore_last_step = time.time()
        self._explore_last_sweep_at = self._explore_last_step
        return self.mini_map_status()

    def stop_mini_map(self, *, update_last_command: bool = True) -> Dict[str, Any]:
        with self._lock:
            self._mini_map_active = False
        self._clear_manual_motion()
        self._explore_phase = "forward"
        if update_last_command:
            self.last_command = "minimap:stop"
        return self.mini_map_status()

    def reset_mini_map(self) -> Dict[str, Any]:
        with self._lock:
            self._mini_map = None
            self._mini_map_active = False
            self._mini_map_completed = False
            self._mini_map_started_at = None
            self._mini_map_completed_at = None
            self._mini_map_frames = 0
            self._mini_map_distance_m = 0.0
            self._mini_map_last_pose = None
        self._clear_manual_motion()
        self._explore_phase = "forward"
        self._explore_turn_remaining = 0.0
        self._explore_last_step = 0.0
        self._explore_last_sweep_at = 0.0
        self.last_command = "minimap:reset"
        return self.mini_map_status()

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
        if enabled:
            self.stop_mini_map(update_last_command=False)
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
        if self._latest_map is None and (
            self._latest_scan_map is None or self._latest_scan_stamp is None or (time.time() - self._latest_scan_stamp) > 2.5
        ):
            self._poll_scan_from_cli()
        with self._lock:
            prefer_mini_map = self._mini_map is not None and (
                self._mini_map_active or self._mini_map_completed or self._mini_map_started_at is not None
            )
            if prefer_mini_map:
                payload = dict(self._mini_map)
            elif self._latest_map is not None:
                payload = dict(self._latest_map)
            elif self._mini_map_has_data(self._mini_map):
                payload = dict(self._mini_map)
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

    def _cached_server_connected(self) -> bool:
        """Return cached server connectivity; refresh at most every 15 s to avoid blocking status polls."""
        if not self.assistant_enabled:
            self._server_connected = False
            return False
        now = time.time()
        if (now - self._server_check_at) > 15.0:
            self._server_connected = self.check_server()
            self._server_check_at = now
        return self._server_connected

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
        self.stop_mini_map(update_last_command=False)
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

        self._set_manual_motion(linear_x, linear_y, angular_z)

    def go_waypoint(self, name: str) -> None:
        self.last_command = f"nav:{name}"
        self.stop_mini_map(update_last_command=False)
        self.set_follow_enabled(False, update_last_command=False)
        self._clear_manual_motion()
        if self.ros2_connected and self._waypoint_goal_pub is not None:
            msg = String()
            msg.data = name
            self._waypoint_goal_pub.publish(msg)

    def run_destination(self, name: str) -> None:
        self.last_command = f"destination:{name}"
        self.stop_mini_map(update_last_command=False)
        self.set_follow_enabled(False, update_last_command=False)
        self._clear_manual_motion()
        if self.ros2_connected and self._destination_goal_pub is not None:
            msg = String()
            msg.data = name
            self._destination_goal_pub.publish(msg)

    def run_route(self, name: str, sequence: List[str]) -> Dict[str, Any]:
        cleaned_sequence = self._normalize_sequence(sequence)
        if not cleaned_sequence:
            raise ValueError("Route sequence is empty.")
        data = self._load_waypoints()
        available = set(data.get("waypoints", {}).keys())
        missing = [item for item in cleaned_sequence if item not in available]
        if missing:
            raise ValueError(f"Unknown checkpoints in route: {', '.join(missing)}")

        self.last_command = f"route:{name}"
        self.stop_mini_map(update_last_command=False)
        self.set_follow_enabled(False, update_last_command=False)
        self._clear_manual_motion()

        if self.ros2_connected and self._destination_goal_pub is not None:
            msg = String()
            msg.data = json.dumps(
                {"name": name or "route_now", "sequence": cleaned_sequence},
                ensure_ascii=True,
            )
            self._destination_goal_pub.publish(msg)
        return {
            "name": name or "route_now",
            "sequence": cleaned_sequence,
        }

    def save_waypoint(
        self,
        name: str,
        x: Optional[float],
        y: Optional[float],
        theta: float,
        description: str,
    ) -> Dict[str, Any]:
        name = name.strip()
        if not name:
            raise ValueError("Checkpoint name is required.")
        if x is None or y is None:
            pose = self.current_pose()
            if pose is None:
                raise ValueError("Current pose is not available.")
            x = pose["x"]
            y = pose["y"]
            theta = pose["theta"]

        if not math.isfinite(float(x)) or not math.isfinite(float(y)) or not math.isfinite(float(theta)):
            raise ValueError("Checkpoint pose must be finite numbers.")

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

    def delete_waypoint(self, name: str) -> Dict[str, Any]:
        cleaned_name = name.strip()
        data = self._load_waypoints()
        waypoints = data.setdefault("waypoints", {})
        if cleaned_name not in waypoints:
            raise ValueError(f"Checkpoint '{cleaned_name}' does not exist.")

        del waypoints[cleaned_name]

        destinations = data.setdefault("destinations", {})
        updated_destinations: Dict[str, Any] = {}
        removed_destinations: List[str] = []
        for destination_name, destination in destinations.items():
            sequence = [
                item
                for item in destination.get("sequence", [])
                if item != cleaned_name
            ]
            if not sequence:
                removed_destinations.append(destination_name)
                continue
            updated_destinations[destination_name] = {
                **destination,
                "sequence": sequence,
            }
        data["destinations"] = updated_destinations

        self.last_command = f"delete_waypoint:{cleaned_name}"
        self._save_waypoints(data)

        if self.ros2_connected and self._waypoint_delete_pub is not None:
            msg = String()
            msg.data = cleaned_name
            self._waypoint_delete_pub.publish(msg)
        if self.ros2_connected and self._destination_delete_pub is not None:
            for destination_name in removed_destinations:
                msg = String()
                msg.data = destination_name
                self._destination_delete_pub.publish(msg)

        return {
            "deleted": cleaned_name,
            "removed_destinations": removed_destinations,
        }

    def clear_waypoints(self) -> Dict[str, Any]:
        data = self._load_waypoints()
        cleared_waypoints = len(data.get("waypoints", {}))
        cleared_destinations = len(data.get("destinations", {}))
        data["waypoints"] = {}
        data["destinations"] = {}
        self.last_command = "clear_waypoints"
        self._save_waypoints(data)

        if self.ros2_connected and self._waypoint_clear_pub is not None:
            msg = String()
            msg.data = "clear"
            self._waypoint_clear_pub.publish(msg)

        return {
            "cleared_waypoints": cleared_waypoints,
            "cleared_destinations": cleared_destinations,
        }

    def list_waypoints(self) -> List[Dict[str, Any]]:
        waypoints = self._load_waypoints().get("waypoints", {})
        items = [
            {
                "name": name,
                "x": float(item.get("pose", {}).get("x", 0.0)),
                "y": float(item.get("pose", {}).get("y", 0.0)),
                "theta": float(item.get("pose", {}).get("theta", 0.0)),
                "description": item.get("description", ""),
            }
            for name, item in waypoints.items()
        ]
        return sorted(items, key=lambda item: item["name"])

    def save_destination(self, name: str, sequence: List[str], description: str) -> Dict[str, Any]:
        name = name.strip()
        if not name:
            raise ValueError("Route name is required.")
        cleaned_sequence = self._normalize_sequence(sequence)
        if not cleaned_sequence:
            raise ValueError("Select at least one checkpoint for the route.")

        data = self._load_waypoints()
        available = set(data.get("waypoints", {}).keys())
        missing = [item for item in cleaned_sequence if item not in available]
        if missing:
            raise ValueError(f"Unknown checkpoints in route: {', '.join(missing)}")

        data.setdefault("destinations", {})
        data["destinations"][name] = {
            "sequence": cleaned_sequence,
            "description": description or f"{name} route",
        }
        self.last_command = f"save_destination:{name}"
        self._save_waypoints(data)

        if self.ros2_connected and self._destination_save_pub is not None:
            msg = String()
            msg.data = json.dumps(
                {
                    "name": name,
                    "sequence": cleaned_sequence,
                    "description": description or f"{name} route",
                },
                ensure_ascii=True,
            )
            self._destination_save_pub.publish(msg)

        return data["destinations"][name]

    def delete_destination(self, name: str) -> None:
        cleaned_name = name.strip()
        data = self._load_waypoints()
        destinations = data.setdefault("destinations", {})
        if cleaned_name not in destinations:
            raise ValueError(f"Route '{cleaned_name}' does not exist.")

        del destinations[cleaned_name]
        self.last_command = f"delete_destination:{cleaned_name}"
        self._save_waypoints(data)

        if self.ros2_connected and self._destination_delete_pub is not None:
            msg = String()
            msg.data = cleaned_name
            self._destination_delete_pub.publish(msg)

    def list_destinations(self) -> List[Dict[str, Any]]:
        data = self._load_waypoints()
        destinations = data.get("destinations", {})
        items = []
        for name, item in destinations.items():
            sequence = self._normalize_sequence(item.get("sequence", []))
            items.append(
                {
                    "name": name,
                    "sequence": sequence,
                    "description": item.get("description", ""),
                    "stops": len(sequence),
                }
            )
        return sorted(items, key=lambda item: item["name"])

    def _normalize_sequence(self, sequence: List[str]) -> List[str]:
        return [item.strip() for item in sequence if str(item).strip()]

    def _load_waypoints(self) -> Dict[str, Any]:
        if not WAYPOINT_FILE.exists():
            return {"waypoints": {}, "destinations": {}, "constraints": {}}
        with WAYPOINT_FILE.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {"waypoints": {}, "destinations": {}, "constraints": {}}

    def _save_waypoints(self, data: Dict[str, Any]) -> None:
        WAYPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with WAYPOINT_FILE.open("w", encoding="utf-8") as file:
            yaml.safe_dump(data, file, allow_unicode=True, sort_keys=False)


bridge = PanelBridge()
app = FastAPI(title="BuddyBot Pi5 Panel")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def disable_browser_cache(request, call_next):
    response = await call_next(request)
    path = request.url.path or "/"
    if path == "/" or path.startswith("/api") or path.startswith("/static"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.get("/")
def root():
    return FileResponse(INDEX_FILE, headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"})


@app.get("/api/version")
def api_version():
    return {
        "panel_build": PANEL_BUILD,
        "panel_static_dir": str(STATIC_DIR),
        "waypoint_file": str(WAYPOINT_FILE),
    }


@app.get("/api/status")
def api_status():
    return bridge.status()


@app.get("/api/map")
def api_map():
    return bridge.get_map_payload()


@app.get("/api/minimap")
def api_minimap():
    return bridge.mini_map_status()


@app.post("/api/minimap/start")
def api_start_minimap():
    return bridge.start_mini_map()


@app.post("/api/minimap/stop")
def api_stop_minimap():
    return bridge.stop_mini_map()


@app.delete("/api/minimap")
def api_reset_minimap():
    return bridge.reset_mini_map()


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
    try:
        waypoint = bridge.save_waypoint(
            request.name,
            request.x,
            request.y,
            request.theta,
            request.description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"saved": True, "waypoint": waypoint, "items": bridge.list_waypoints()}


@app.post("/api/waypoints/current")
def api_save_current_waypoint(request: CurrentPoseWaypointRequest):
    try:
        waypoint = bridge.save_waypoint(request.name, None, None, 0.0, request.description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"saved": True, "waypoint": waypoint, "items": bridge.list_waypoints()}


@app.delete("/api/waypoints/{name}")
def api_delete_waypoint(name: str):
    try:
        result = bridge.delete_waypoint(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True, **result, "items": bridge.list_waypoints(), "destinations": bridge.list_destinations()}


@app.delete("/api/waypoints")
def api_clear_waypoints():
    result = bridge.clear_waypoints()
    return {"cleared": True, **result, "items": bridge.list_waypoints(), "destinations": bridge.list_destinations()}


@app.post("/api/go")
def api_go(request: WaypointGoRequest):
    bridge.go_waypoint(request.name)
    return {"success": True, "message": f"Sent navigation request to {request.name}."}


@app.post("/api/navigation/cancel")
def api_cancel_navigation():
    bridge.cancel_navigation()
    return {"success": True, "message": "Navigation cancelled."}


@app.get("/api/destinations")
def api_destinations():
    return {"items": bridge.list_destinations()}


@app.post("/api/destinations")
def api_save_destination(request: DestinationSaveRequest):
    try:
        destination = bridge.save_destination(request.name, request.sequence, request.description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"saved": True, "destination": destination, "items": bridge.list_destinations()}


@app.delete("/api/destinations/{name}")
def api_delete_destination(name: str):
    try:
        bridge.delete_destination(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"deleted": True, "items": bridge.list_destinations()}


@app.post("/api/destinations/go")
def api_go_destination(request: DestinationGoRequest):
    bridge.run_destination(request.name)
    return {"success": True, "message": f"Sent route {request.name}."}


@app.post("/api/routes/run")
def api_run_route(request: RouteRunRequest):
    try:
        route = bridge.run_route(request.name, request.sequence)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "route": route, "message": f"Sent ad-hoc route {route['name']}."}


def main() -> None:
    host = os.getenv("BUDDYBOT_PANEL_HOST", "0.0.0.0")
    port = int(os.getenv("BUDDYBOT_PANEL_PORT", "8090"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
