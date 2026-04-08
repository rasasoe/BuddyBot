#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_DIR="$ROOT_DIR/software/pi5/ros2_ws"
ROS_DISTRO_NAME="${ROS_DISTRO:-jazzy}"

safe_source() {
  local target="$1"
  set +u
  # shellcheck disable=SC1090
  source "$target"
  set -u
}

configure_offline_ros() {
  export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}"
  export ROS_LOCALHOST_ONLY=0
  unset ROS_DISCOVERY_SERVER
  unset ROS_SUPER_CLIENT
}

if [[ ! -f "/opt/ros/$ROS_DISTRO_NAME/setup.bash" ]]; then
  echo "[one-terminal] error: /opt/ros/$ROS_DISTRO_NAME/setup.bash not found"
  exit 1
fi

if [[ ! -f "$WS_DIR/install/setup.bash" ]]; then
  echo "[one-terminal] error: workspace is not built yet"
  echo "[one-terminal] run: bash $ROOT_DIR/scripts/setup_pi5.sh"
  exit 1
fi

safe_source "/opt/ros/$ROS_DISTRO_NAME/setup.bash"
safe_source "$WS_DIR/install/setup.bash"
configure_offline_ros

echo "[one-terminal] cleaning stale ROS processes"
pkill -f "ros2 launch sllidar_ros2" 2>/dev/null || true
pkill -f "/home/pi/ros2_ws/install/sllidar_ros2/lib/sllidar_ros2/sllidar_node" 2>/dev/null || true
pkill -f "slam_toolbox" 2>/dev/null || true
sleep 2

echo "[one-terminal] resetting ROS discovery"
ros2 daemon stop >/dev/null 2>&1 || true
ros2 daemon start >/dev/null 2>&1 || true
sleep 2

echo "[one-terminal] probing devices"
eval "$(python3 "$ROOT_DIR/scripts/probe_pi5_devices.py" --shell)"
export BUDDYBOT_PICO_PORT="${PICO_PORT:-}"
export BUDDYBOT_LIDAR_PORT="${LIDAR_PORT:-}"
export BUDDYBOT_CAMERA_DEVICE="${CAMERA_DEVICE:-}"
export BUDDYBOT_FORCE_LIDAR_START=1
export BUDDYBOT_PREFLIGHT_CHECK=0

echo "[one-terminal] pico: ${BUDDYBOT_PICO_PORT:-none}"
echo "[one-terminal] lidar: ${BUDDYBOT_LIDAR_PORT:-none}"
echo "[one-terminal] camera: ${BUDDYBOT_CAMERA_DEVICE:-none}"
echo "[one-terminal] starting mapping stack"

exec bash "$ROOT_DIR/scripts/start_all_pi5.sh" mapping
