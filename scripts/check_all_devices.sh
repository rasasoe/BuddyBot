#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_DIR="$ROOT_DIR/software/pi5/ros2_ws"
ROS_DISTRO_NAME="${ROS_DISTRO:-jazzy}"
TMP_DIR="$(mktemp -d)"

cleanup() {
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  rm -rf "$TMP_DIR"
}

trap cleanup EXIT INT TERM

safe_source() {
  local target="$1"
  set +u
  # shellcheck disable=SC1090
  source "$target"
  set -u
}

safe_source "/opt/ros/$ROS_DISTRO_NAME/setup.bash"
safe_source "$WS_DIR/install/setup.bash"
ros2 daemon stop >/dev/null 2>&1 || true
ros2 daemon start >/dev/null 2>&1 || true
sleep 2
eval "$(python3 "$ROOT_DIR/scripts/probe_pi5_devices.py" --shell)"

PIDS=()
CAMERA_START_DELAY="${BUDDYBOT_CAMERA_START_DELAY:-4}"
LIDAR_SETTLE_DELAY="${BUDDYBOT_LIDAR_SETTLE_DELAY:-6}"
CAMERA_WIDTH="${BUDDYBOT_CAMERA_WIDTH:-320}"
CAMERA_HEIGHT="${BUDDYBOT_CAMERA_HEIGHT:-240}"
CAMERA_FPS="${BUDDYBOT_CAMERA_FPS:-15}"
CAMERA_PUBLISH_RATE="${BUDDYBOT_CAMERA_PUBLISH_RATE:-10}"

echo "[check] detected devices"
echo "  pico   : ${PICO_PORT:-none}"
echo "  lidar  : ${LIDAR_PORT:-none}"
echo "  camera : ${CAMERA_DEVICE:-none}"
echo "  mic    : ${MIC_AVAILABLE:-0}"
echo "  lidar settle delay : ${LIDAR_SETTLE_DELAY}s"
echo "  camera start delay : ${CAMERA_START_DELAY}s"
echo "  camera profile : ${CAMERA_WIDTH}x${CAMERA_HEIGHT} @ ${CAMERA_FPS}fps publish ${CAMERA_PUBLISH_RATE}Hz"
echo

start_bg() {
  local name="$1"
  shift
  echo "[check] starting $name"
  "$@" > "$TMP_DIR/$name.log" 2>&1 &
  PIDS+=("$!")
  sleep 2
}

pause_before_step() {
  local seconds="$1"
  local reason="$2"
  if [[ "$seconds" =~ ^[0-9]+$ ]] && (( seconds > 0 )); then
    echo "[check] waiting ${seconds}s before $reason"
    sleep "$seconds"
  fi
}

wait_for_topic() {
  local topic="$1"
  local timeout="${2:-8}"
  local start_ts
  start_ts="$(date +%s)"
  while true; do
    if ros2 topic list 2>/dev/null | grep -q "^$topic$"; then
      return 0
    fi
    if (( $(date +%s) - start_ts >= timeout )); then
      return 1
    fi
    sleep 1
  done
}

wait_for_message() {
  local topic="$1"
  local timeout="${2:-8}"
  timeout "${timeout}s" ros2 topic echo --once "$topic" >/dev/null 2>&1
}

publisher_visible() {
  local node_name="$1"
  local topic_fragment="$2"
  ros2 node info "$node_name" 2>/dev/null | grep -Eq "(^|[[:space:]])/?${topic_fragment}([[:space:]]|$)"
}

echo "[check] pico test"
if [[ -n "${PICO_PORT:-}" ]]; then
  start_bg pico ros2 run buddybot_base pico_bridge_node --ros-args -p serial_port:="${PICO_PORT}"
  if wait_for_topic "/buddybot/pico_status" 6 || publisher_visible "/pico_bridge_node" "/buddybot/pico_status"; then
    echo "  result: PASS (/buddybot/pico_status present)"
  else
    echo "  result: WARN (topic missing, heartbeat may still be alive)"
  fi
else
  echo "  result: FAIL (no Pico port detected)"
fi
echo

echo "[check] lidar test"
if [[ -n "${LIDAR_PORT:-}" ]]; then
  start_bg lidar ros2 launch sllidar_ros2 sllidar_a1_launch.py serial_port:="${LIDAR_PORT}" serial_baudrate:=115200
  pause_before_step "$LIDAR_SETTLE_DELAY" "checking LiDAR scan output"
  if wait_for_message "/scan" 10 || wait_for_topic "/scan" 10 || wait_for_topic "scan" 10 || publisher_visible "/sllidar_node" "scan"; then
    echo "  result: PASS (/scan present)"
  else
    echo "  result: FAIL (/scan missing)"
  fi
else
  echo "  result: FAIL (no LiDAR port detected)"
fi
echo

echo "[check] camera test"
if [[ -n "${CAMERA_DEVICE:-}" ]]; then
  pause_before_step "$CAMERA_START_DELAY" "starting camera after USB devices settle"
  start_bg camera ros2 run buddybot_vision camera_node --ros-args -p device:="${CAMERA_DEVICE}" -p width:="${CAMERA_WIDTH}" -p height:="${CAMERA_HEIGHT}" -p fps:="${CAMERA_FPS}" -p publish_rate:="${CAMERA_PUBLISH_RATE}"
  if wait_for_message "/camera/image_raw" 10 || wait_for_topic "/camera/image_raw" 10 || publisher_visible "/camera_node" "camera/image_raw"; then
    echo "  result: PASS (/camera/image_raw present)"
  else
    echo "  result: FAIL (/camera/image_raw missing)"
  fi
else
  echo "  result: FAIL (no camera device detected)"
fi
echo

echo "[check] microphone test"
if [[ "${MIC_AVAILABLE:-0}" == "1" ]]; then
  echo "  result: PASS (capture device visible)"
else
  echo "  result: FAIL (no capture device visible)"
fi
echo

echo "[check] logs"
for name in pico lidar camera; do
  if [[ -f "$TMP_DIR/$name.log" ]]; then
    echo "===== $name ====="
    tail -n 20 "$TMP_DIR/$name.log" || true
    echo
  fi
done
