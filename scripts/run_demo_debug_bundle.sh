#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_DIR="$ROOT_DIR/software/pi5/ros2_ws"
ROS_DISTRO_NAME="${ROS_DISTRO:-jazzy}"
MODE="${1:-mapping}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BUNDLE_DIR="${BUDDYBOT_DEBUG_DIR:-/tmp/buddybot-debug-$STAMP}"
TOPIC_PIDS=()

safe_source() {
  local target="$1"
  set +u
  # shellcheck disable=SC1090
  source "$target"
  set -u
}

capture_cmd() {
  local name="$1"
  shift
  {
    echo "### $name"
    echo "\$ $*"
    "$@" 2>&1 || true
    echo
  } >> "$BUNDLE_DIR/system_snapshot.log"
}

start_topic_capture() {
  local name="$1"
  local topic="$2"
  local type_name="$3"
  shift 3
  local log_path="$BUNDLE_DIR/$name.log"
  {
    echo "### ros2 topic echo $topic $type_name"
    echo "### started_at $(date '+%Y-%m-%d %H:%M:%S %z')"
    echo
  } > "$log_path"
  if command -v stdbuf >/dev/null 2>&1; then
    nohup env PYTHONUNBUFFERED=1 stdbuf -oL -eL ros2 topic echo "$@" "$topic" "$type_name" >> "$log_path" 2>&1 &
  else
    nohup env PYTHONUNBUFFERED=1 ros2 topic echo "$@" "$topic" "$type_name" >> "$log_path" 2>&1 &
  fi
  TOPIC_PIDS+=("$!")
}

cleanup() {
  if command -v curl >/dev/null 2>&1; then
    capture_cmd panel_status curl -s http://127.0.0.1:8090/api/status
    capture_cmd panel_minimap curl -s http://127.0.0.1:8090/api/minimap
  fi

  for pid in "${TOPIC_PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done

  capture_cmd lsusb lsusb
  if command -v v4l2-ctl >/dev/null 2>&1; then
    capture_cmd v4l2 "v4l2-ctl" "--list-devices"
  fi
  if command -v vcgencmd >/dev/null 2>&1; then
    capture_cmd vcgencmd vcgencmd get_throttled
  fi
  if command -v journalctl >/dev/null 2>&1; then
    capture_cmd kernel journalctl -k -b
  fi

  if command -v ros2 >/dev/null 2>&1; then
    {
      echo "### ros2 node list"
      ros2 node list 2>&1 || true
      echo
      echo "### ros2 topic list"
      ros2 topic list 2>&1 || true
      echo
    } >> "$BUNDLE_DIR/system_snapshot.log"
  fi

  for log_name in panel command_mux pico_bridge camera detector follow_controller lidar voice waypoint_manager slam safety_supervisor mode_manager; do
    log_path="$WS_DIR/log/mapping_panel/$log_name.log"
    if [[ -f "$log_path" ]]; then
      tail -n 200 "$log_path" > "$BUNDLE_DIR/$log_name.tail.log" || true
    fi
  done

  tar -czf "$BUNDLE_DIR.tar.gz" -C "$(dirname "$BUNDLE_DIR")" "$(basename "$BUNDLE_DIR")" 2>/dev/null || true
  echo
  echo "[debug] bundle directory: $BUNDLE_DIR"
  echo "[debug] bundle archive: $BUNDLE_DIR.tar.gz"
  echo "[debug] send me these files if needed:"
  echo "[debug]   $BUNDLE_DIR/system_snapshot.log"
  echo "[debug]   $BUNDLE_DIR/cmd_vel_manual.log"
  echo "[debug]   $BUNDLE_DIR/cmd_vel_final.log"
  echo "[debug]   $BUNDLE_DIR/follow_status.log"
  echo "[debug]   $BUNDLE_DIR/pico_status.log"
  echo "[debug]   $BUNDLE_DIR/command_mux.tail.log"
  echo "[debug]   $BUNDLE_DIR/pico_bridge.tail.log"
}

trap cleanup EXIT INT TERM

mkdir -p "$BUNDLE_DIR"
rm -f "$BUNDLE_DIR"/*.log "$BUNDLE_DIR"/*.txt "$BUNDLE_DIR"/*.gz 2>/dev/null || true

safe_source "/opt/ros/$ROS_DISTRO_NAME/setup.bash"
safe_source "$WS_DIR/install/setup.bash"

capture_cmd repo_head git -C "$ROOT_DIR" rev-parse HEAD
capture_cmd repo_status git -C "$ROOT_DIR" status --short
capture_cmd lsusb lsusb
if command -v v4l2-ctl >/dev/null 2>&1; then
  capture_cmd v4l2 v4l2-ctl --list-devices
fi
if command -v vcgencmd >/dev/null 2>&1; then
  capture_cmd vcgencmd vcgencmd get_throttled
fi
if command -v ros2 >/dev/null 2>&1; then
  capture_cmd topic_info_manual ros2 topic info -v /cmd_vel_manual
  capture_cmd topic_info_final ros2 topic info -v /cmd_vel_final
  capture_cmd topic_info_safety ros2 topic info -v /system/safety_status
  capture_cmd topic_info_lidar ros2 topic info -v /system/lidar_avoidance_status
fi

start_topic_capture cmd_vel_manual /cmd_vel_manual geometry_msgs/msg/Twist
start_topic_capture cmd_vel_final /cmd_vel_final geometry_msgs/msg/Twist
start_topic_capture pico_status /buddybot/pico_status buddybot_msgs/msg/Status
start_topic_capture pico_safety /buddybot/pico_safety_event std_msgs/msg/String
start_topic_capture scan /scan sensor_msgs/msg/LaserScan --qos-reliability best_effort
start_topic_capture camera_image /camera/image_raw sensor_msgs/msg/Image --qos-reliability best_effort
start_topic_capture detector_status /vision/detector_status std_msgs/msg/String
start_topic_capture follow_status /follow/status std_msgs/msg/String
start_topic_capture navigation_status /nav/navigation_status std_msgs/msg/String
start_topic_capture command_status /system/command_status std_msgs/msg/String
start_topic_capture safety_status /system/safety_status std_msgs/msg/String
start_topic_capture lidar_avoidance_status /system/lidar_avoidance_status std_msgs/msg/String

echo "[debug] writing logs to $BUNDLE_DIR"
echo "[debug] run the demo, reproduce the issue, then press Ctrl+C once"
echo "[debug] after shutdown a log bundle will be collected automatically"

cd "$ROOT_DIR"
bash "$ROOT_DIR/scripts/start_all_pi5.sh" "$MODE"
