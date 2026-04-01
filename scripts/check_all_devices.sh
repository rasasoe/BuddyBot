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
eval "$(python3 "$ROOT_DIR/scripts/probe_pi5_devices.py" --shell)"

PIDS=()

echo "[check] detected devices"
echo "  pico   : ${PICO_PORT:-none}"
echo "  lidar  : ${LIDAR_PORT:-none}"
echo "  camera : ${CAMERA_DEVICE:-none}"
echo "  mic    : ${MIC_AVAILABLE:-0}"
echo

start_bg() {
  local name="$1"
  shift
  echo "[check] starting $name"
  "$@" > "$TMP_DIR/$name.log" 2>&1 &
  PIDS+=("$!")
  sleep 2
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

echo "[check] pico test"
if [[ -n "${PICO_PORT:-}" ]]; then
  start_bg pico ros2 run buddybot_base pico_bridge_node --ros-args -p serial_port:="${PICO_PORT}"
  if wait_for_topic "/buddybot/pico_status" 6; then
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
  if wait_for_topic "/scan" 8; then
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
  start_bg camera ros2 run buddybot_vision camera_node --ros-args -p device:="${CAMERA_DEVICE}"
  if wait_for_topic "/camera/image_raw" 8; then
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
