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

PIDS=()

start_node() {
  local name="$1"
  shift
  echo "[demo] starting $name"
  "$@" > "$LOG_DIR/$name.log" 2>&1 &
  PIDS+=("$!")
  sleep 1
}

cleanup() {
  echo
  echo "[demo] stopping nodes"
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}

trap cleanup EXIT INT TERM

start_node pico_bridge ros2 run buddybot_base pico_bridge_node
start_node command_mux ros2 run buddybot_system command_mux_node
start_node mode_manager ros2 run buddybot_system mode_manager_node
start_node safety_supervisor ros2 run buddybot_system safety_supervisor_node
start_node lidar_avoidance ros2 run buddybot_system lidar_avoidance_node
start_node camera ros2 run buddybot_vision camera_node
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

echo
echo "[demo] offline demo is running"
echo "[demo] panel url: http://127.0.0.1:8090"
echo "[demo] phone url: http://PI5_IP:8090"
echo "[demo] logs: $LOG_DIR"
echo "[demo] press Ctrl+C to stop everything"

while true; do
  sleep 2
done
