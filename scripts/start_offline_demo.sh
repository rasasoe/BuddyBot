#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_DIR="$ROOT_DIR/software/pi5/ros2_ws"
LOG_DIR="$WS_DIR/log/offline_demo"
ROS_DISTRO_NAME="${ROS_DISTRO:-jazzy}"

mkdir -p "$LOG_DIR"

if [[ ! -f "/opt/ros/$ROS_DISTRO_NAME/setup.bash" ]]; then
  echo "[demo] error: /opt/ros/$ROS_DISTRO_NAME/setup.bash not found"
  exit 1
fi

if [[ ! -f "$WS_DIR/install/setup.bash" ]]; then
  echo "[demo] error: workspace is not built yet"
  echo "[demo] run: bash $ROOT_DIR/scripts/setup_pi5.sh"
  exit 1
fi

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
LIDAR_STARTED=0
CAMERA_START_DELAY="${BUDDYBOT_CAMERA_START_DELAY:-4}"
LIDAR_SETTLE_DELAY="${BUDDYBOT_LIDAR_SETTLE_DELAY:-6}"
CAMERA_WIDTH="${BUDDYBOT_CAMERA_WIDTH:-320}"
CAMERA_HEIGHT="${BUDDYBOT_CAMERA_HEIGHT:-240}"
CAMERA_FPS="${BUDDYBOT_CAMERA_FPS:-15.0}"
CAMERA_PUBLISH_RATE="${BUDDYBOT_CAMERA_PUBLISH_RATE:-10.0}"

start_node() {
  local name="$1"
  shift
  echo "[demo] starting $name"
  "$@" > "$LOG_DIR/$name.log" 2>&1 &
  PIDS+=("$!")
  sleep 1
}

pause_before_node() {
  local seconds="$1"
  local reason="$2"
  if [[ "$seconds" =~ ^[0-9]+$ ]] && (( seconds > 0 )); then
    echo "[demo] waiting ${seconds}s before $reason"
    sleep "$seconds"
  fi
}

cleanup() {
  echo
  echo "[demo] stopping nodes"
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}

trap cleanup EXIT INT TERM

scan_available() {
  ros2 topic list 2>/dev/null | grep -Eq '^(/)?scan$' && return 0
  ros2 node info /sllidar_node 2>/dev/null | grep -Eq '(^|[[:space:]])/?scan([[:space:]]|$)'
}

camera_available() {
  ros2 topic list 2>/dev/null | grep -q '^/camera/image_raw$' && return 0
  ros2 node info /camera_node 2>/dev/null | grep -Eq '(^|[[:space:]])/?camera/image_raw([[:space:]]|$)'
}

start_lidar_if_available() {
  local serial_port="${BUDDYBOT_LIDAR_PORT:-${LIDAR_PORT:-}}"
  local serial_baudrate="${BUDDYBOT_LIDAR_BAUDRATE:-115200}"
  local pkg_prefix=""
  local pkg_share=""
  local launch_file=""

  if scan_available; then
    echo "[demo] lidar scan already available"
    return
  fi

  if ! pkg_prefix="$(ros2 pkg prefix sllidar_ros2 2>/dev/null)"; then
    echo "[demo] lidar autostart skipped: sllidar_ros2 is not installed"
    return
  fi

  pkg_share="$pkg_prefix/share/sllidar_ros2"
  if [[ -z "$serial_port" ]]; then
    for candidate in /dev/ttyUSB0 /dev/ttyUSB1 /dev/ttyACM0 /dev/ttyACM1; do
      if [[ -e "$candidate" ]]; then
        serial_port="$candidate"
        break
      fi
    done
  fi

  if [[ -z "$serial_port" ]]; then
    echo "[demo] lidar autostart skipped: no serial device found"
    return
  fi

  for candidate in sllidar_a1_launch.py view_sllidar_a1_launch.py sllidar_launch.py view_sllidar_launch.py; do
    if [[ -f "$pkg_share/launch/$candidate" ]]; then
      launch_file="$candidate"
      break
    fi
  done

  if [[ -z "$launch_file" ]]; then
    echo "[demo] lidar autostart skipped: no known sllidar launch file found"
    return
  fi

  start_node lidar ros2 launch sllidar_ros2 "$launch_file" serial_port:="$serial_port" serial_baudrate:="$serial_baudrate"
  LIDAR_STARTED=1
}

echo "[demo] detected Pico port: ${PICO_PORT:-none}"
echo "[demo] detected LiDAR port: ${LIDAR_PORT:-none}"
echo "[demo] detected camera device: ${CAMERA_DEVICE:-none}"
echo "[demo] microphone available: ${MIC_AVAILABLE:-0}"
echo "[demo] AI server: ${AI_SERVER_STATE:-unknown}"
echo "[demo] lidar settle delay: ${LIDAR_SETTLE_DELAY}s"
echo "[demo] camera start delay: ${CAMERA_START_DELAY}s"
echo "[demo] camera profile: ${CAMERA_WIDTH}x${CAMERA_HEIGHT} @ ${CAMERA_FPS}fps publish ${CAMERA_PUBLISH_RATE}Hz"

start_lidar_if_available
if [[ "$LIDAR_STARTED" -eq 1 ]]; then
  pause_before_node "$LIDAR_SETTLE_DELAY" "starting camera after lidar spin-up"
fi
if [[ -n "${PICO_PORT:-}" ]]; then
  start_node pico_bridge ros2 run buddybot_base pico_bridge_node --ros-args -p serial_port:="${PICO_PORT}"
else
  start_node pico_bridge ros2 run buddybot_base pico_bridge_node
fi
start_node command_mux ros2 run buddybot_system command_mux_node
start_node mode_manager ros2 run buddybot_system mode_manager_node
start_node safety_supervisor ros2 run buddybot_system safety_supervisor_node
start_node lidar_avoidance ros2 run buddybot_system lidar_avoidance_node
pause_before_node "$CAMERA_START_DELAY" "starting camera"
if [[ -n "${CAMERA_DEVICE:-}" ]]; then
  start_node camera ros2 run buddybot_vision camera_node --ros-args -p device:="${CAMERA_DEVICE}" -p width:="${CAMERA_WIDTH}" -p height:="${CAMERA_HEIGHT}" -p fps:="${CAMERA_FPS}" -p publish_rate:="${CAMERA_PUBLISH_RATE}"
else
  start_node camera ros2 run buddybot_vision camera_node --ros-args -p width:="${CAMERA_WIDTH}" -p height:="${CAMERA_HEIGHT}" -p fps:="${CAMERA_FPS}" -p publish_rate:="${CAMERA_PUBLISH_RATE}"
fi
start_node detector ros2 run buddybot_vision detector_node
start_node follow_controller ros2 run buddybot_vision follow_controller_node
start_node waypoint_manager ros2 run buddybot_nav waypoint_manager_node
start_node panel ros2 run buddybot_panel panel_server

for _ in {1..15}; do
  if python3 - <<'PY'
import socket
s = socket.socket()
try:
    s.settimeout(0.5)
    s.connect(("127.0.0.1", 8090))
    print("ok")
    raise SystemExit(0)
except OSError:
    raise SystemExit(1)
finally:
    s.close()
PY
  then
    break
  fi
  sleep 1
done

if ! python3 - <<'PY'
import socket
s = socket.socket()
try:
    s.settimeout(0.5)
    s.connect(("127.0.0.1", 8090))
    raise SystemExit(0)
except OSError:
    raise SystemExit(1)
finally:
    s.close()
PY
then
  echo "[demo] panel did not open on 127.0.0.1:8090"
  echo "[demo] last panel log:"
  tail -n 120 "$LOG_DIR/panel.log" || true
  exit 1
fi

sleep 2
if ! camera_available; then
  echo "[demo] warning: /camera/image_raw is not being published yet"
  echo "[demo] check: tail -n 120 $LOG_DIR/camera.log"
fi

if [[ "$LIDAR_STARTED" -eq 1 ]] && ! scan_available; then
  echo "[demo] warning: lidar driver started but /scan is still missing"
  echo "[demo] check: tail -n 120 $LOG_DIR/lidar.log"
fi

echo
echo "[demo] offline demo is running"
echo "[demo] panel url: http://127.0.0.1:8090"
echo "[demo] phone url: http://PI5_IP:8090"
if [[ "$LIDAR_STARTED" -eq 1 ]]; then
  echo "[demo] lidar driver: auto-started"
else
  echo "[demo] lidar driver: not started by this script"
fi
echo "[demo] logs: $LOG_DIR"
echo "[demo] press Ctrl+C to stop everything"

while true; do
  sleep 2
done
