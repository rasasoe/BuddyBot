#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_DIR="$ROOT_DIR/software/pi5/ros2_ws"
LOG_DIR="$WS_DIR/log/manual_lidar_boot"
ROS_DISTRO_NAME="${ROS_DISTRO:-jazzy}"
LIDAR_PORT="${BUDDYBOT_LIDAR_PORT:-/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0}"
LIDAR_BAUDRATE="${BUDDYBOT_LIDAR_BAUDRATE:-115200}"
SCAN_WAIT_SECONDS="${BUDDYBOT_SCAN_WAIT_SECONDS:-12}"

mkdir -p "$LOG_DIR"

safe_source() {
  local target="$1"
  set +u
  # shellcheck disable=SC1090
  source "$target"
  set -u
}

if [[ ! -f "/opt/ros/$ROS_DISTRO_NAME/setup.bash" ]]; then
  echo "[real-map] error: /opt/ros/$ROS_DISTRO_NAME/setup.bash not found"
  exit 1
fi

if [[ ! -f "$WS_DIR/install/setup.bash" ]]; then
  echo "[real-map] error: workspace is not built yet"
  echo "[real-map] run: bash $ROOT_DIR/scripts/setup_pi5.sh"
  exit 1
fi

safe_source "/opt/ros/$ROS_DISTRO_NAME/setup.bash"
safe_source "$WS_DIR/install/setup.bash"

echo "[real-map] resetting ROS discovery"
ros2 daemon stop >/dev/null 2>&1 || true
ros2 daemon start >/dev/null 2>&1 || true
sleep 2

echo "[real-map] starting detached LiDAR driver"
nohup bash -lc "
  source /opt/ros/$ROS_DISTRO_NAME/setup.bash
  source '$WS_DIR/install/setup.bash'
  exec ros2 launch sllidar_ros2 sllidar_a1_launch.py serial_port:='$LIDAR_PORT' serial_baudrate:='$LIDAR_BAUDRATE'
" > "$LOG_DIR/lidar.log" 2>&1 < /dev/null &

echo "[real-map] waiting for /scan (${SCAN_WAIT_SECONDS}s timeout)"
for _ in $(seq 1 "$SCAN_WAIT_SECONDS"); do
  if ros2 topic list 2>/dev/null | grep -q '^/scan$'; then
    echo "[real-map] /scan is available"
    exec bash "$ROOT_DIR/scripts/start_all_pi5.sh" mapping
  fi
  sleep 1
done

echo "[real-map] error: /scan did not appear"
echo "[real-map] check: tail -n 120 $LOG_DIR/lidar.log"
exit 1
