#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_DIR="$ROOT_DIR/software/pi5/ros2_ws"
ROS_DISTRO_NAME="${ROS_DISTRO:-jazzy}"
MODE="${1:-demo}"
RUN_PREFLIGHT="${BUDDYBOT_PREFLIGHT_CHECK:-1}"
DISABLE_CAMERA="${BUDDYBOT_DISABLE_CAMERA:-0}"
DISABLE_PICO="${BUDDYBOT_DISABLE_PICO:-0}"

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

usage() {
  echo "Usage: bash scripts/start_all_pi5.sh [demo|mapping]"
}

if [[ ! -f "/opt/ros/$ROS_DISTRO_NAME/setup.bash" ]]; then
  echo "[all] error: /opt/ros/$ROS_DISTRO_NAME/setup.bash not found"
  exit 1
fi

if [[ ! -f "$WS_DIR/install/setup.bash" ]]; then
  echo "[all] error: workspace is not built yet"
  echo "[all] run: bash $ROOT_DIR/scripts/setup_pi5.sh"
  exit 1
fi

case "$MODE" in
  demo)
    TARGET_SCRIPT="$ROOT_DIR/scripts/start_offline_demo.sh"
    ;;
  mapping)
    TARGET_SCRIPT="$ROOT_DIR/scripts/start_mapping_panel.sh"
    ;;
  *)
    usage
    exit 1
    ;;
esac

safe_source "/opt/ros/$ROS_DISTRO_NAME/setup.bash"
safe_source "$WS_DIR/install/setup.bash"
configure_offline_ros

echo "[all] resetting ROS discovery"
ros2 daemon stop >/dev/null 2>&1 || true
ros2 daemon start >/dev/null 2>&1 || true
sleep 2

echo "[all] probing Pi5 devices"
eval "$(python3 "$ROOT_DIR/scripts/probe_pi5_devices.py" --shell)"
echo "PICO_PORT=${PICO_PORT:-}"
echo "LIDAR_PORT=${LIDAR_PORT:-}"
echo "CAMERA_DEVICE=${CAMERA_DEVICE:-}"
echo "MIC_AVAILABLE=${MIC_AVAILABLE:-}"
echo "AI_SERVER_STATE=${AI_SERVER_STATE:-}"
echo "SERIAL_CANDIDATES=${SERIAL_CANDIDATES:-}"
echo "SERIAL_BY_ID=${SERIAL_BY_ID:-}"
echo "SERIAL_BY_PATH=${SERIAL_BY_PATH:-}"
echo "V4L_BY_ID=${V4L_BY_ID:-}"
echo "MIC_INFO=${MIC_INFO:-}"
echo
echo "[all] camera disabled: $DISABLE_CAMERA"
echo "[all] pico disabled: $DISABLE_PICO"
echo "[all] ROS_DOMAIN_ID: ${ROS_DOMAIN_ID}"
echo "[all] ROS_LOCALHOST_ONLY: ${ROS_LOCALHOST_ONLY}"
echo "[all] ROS_DISCOVERY_SERVER: ${ROS_DISCOVERY_SERVER:-unset}"

export BUDDYBOT_PICO_PORT="${PICO_PORT:-}"
export BUDDYBOT_LIDAR_PORT="${LIDAR_PORT:-}"
export BUDDYBOT_CAMERA_DEVICE="${CAMERA_DEVICE:-}"

if [[ "$RUN_PREFLIGHT" == "1" ]]; then
  echo "[all] running preflight device check"
  bash "$ROOT_DIR/scripts/check_all_devices.sh" || true
  echo
  echo "[all] resetting ROS discovery after preflight"
  ros2 daemon stop >/dev/null 2>&1 || true
  ros2 daemon start >/dev/null 2>&1 || true
  sleep 2
  export BUDDYBOT_FORCE_LIDAR_START=1
fi

echo "[all] starting mode: $MODE"
exec bash "$TARGET_SCRIPT"
