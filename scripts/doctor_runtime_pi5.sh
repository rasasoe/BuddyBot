#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_DIR="$ROOT_DIR/software/pi5/ros2_ws"
ROS_DISTRO_NAME="${ROS_DISTRO:-jazzy}"

if [[ -f "/opt/ros/$ROS_DISTRO_NAME/setup.bash" ]]; then
  set +u
  # shellcheck disable=SC1090
  source "/opt/ros/$ROS_DISTRO_NAME/setup.bash"
  [[ -f "$WS_DIR/install/setup.bash" ]] && source "$WS_DIR/install/setup.bash"
  set -u
fi

echo "[runtime] device probe"
python3 "$ROOT_DIR/scripts/probe_pi5_devices.py"
echo

echo "[runtime] ros topics"
for topic in /buddybot/pico_status /camera/image_raw /scan /map /voice/text /voice/response; do
  if ros2 topic list 2>/dev/null | grep -q "^$topic$"; then
    echo "  $topic : present"
  else
    echo "  $topic : missing"
  fi
done
echo

echo "[runtime] recent logs"
for log_name in pico_bridge camera lidar panel; do
  for dir_name in offline_demo mapping_panel; do
    log_path="$WS_DIR/log/$dir_name/$log_name.log"
    if [[ -f "$log_path" ]]; then
      echo "===== $log_path ====="
      tail -n 20 "$log_path" || true
      echo
      break
    fi
  done
done
