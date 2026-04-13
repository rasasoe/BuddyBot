#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_DIR="$ROOT_DIR/software/pi5/ros2_ws"
ROS_DISTRO_NAME="${ROS_DISTRO:-jazzy}"

echo "[setup] repo root: $ROOT_DIR"
echo "[setup] workspace: $WS_DIR"
echo "[setup] ROS distro: $ROS_DISTRO_NAME"

if [[ ! -f "/opt/ros/$ROS_DISTRO_NAME/setup.bash" ]]; then
  echo "[setup] error: /opt/ros/$ROS_DISTRO_NAME/setup.bash not found"
  echo "[setup] install ROS 2 $ROS_DISTRO_NAME first, then run this script again"
  exit 1
fi

safe_source() {
  local target="$1"
  set +u
  # shellcheck disable=SC1090
  source "$target"
  set -u
}

sudo apt update
sudo apt install -y \
  alsa-utils \
  espeak-ng \
  python3-colcon-common-extensions \
  python3-pyaudio \
  python3-pocketsphinx \
  python3-speechrecognition \
  python3-serial \
  python3-requests \
  python3-yaml \
  python3-fastapi \
  python3-uvicorn \
  python3-opencv \
  v4l-utils \
  ros-"$ROS_DISTRO_NAME"-cv-bridge \
  ros-"$ROS_DISTRO_NAME"-navigation2 \
  ros-"$ROS_DISTRO_NAME"-nav2-bringup \
  ros-"$ROS_DISTRO_NAME"-slam-toolbox

safe_source "/opt/ros/$ROS_DISTRO_NAME/setup.bash"

bash "$ROOT_DIR/scripts/doctor_pi5.sh" --fix

cd "$WS_DIR"
colcon build --symlink-install
safe_source "$WS_DIR/install/setup.bash"

echo
echo "[setup] done"
echo "[setup] next:"
echo "  bash $ROOT_DIR/scripts/start_offline_demo.sh"
