#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${1:-}"

if [[ -z "${PORT}" ]]; then
  if command -v python3 >/dev/null 2>&1 && [[ -f "${ROOT_DIR}/scripts/probe_pi5_devices.py" ]]; then
    PORT="$(python3 "${ROOT_DIR}/scripts/probe_pi5_devices.py" 2>/dev/null | awk -F= '/^PICO_PORT=/{print $2; exit}')"
  fi
fi
PORT="${PORT:-/dev/ttyACM0}"

echo "[pico-motor-test] port: ${PORT}"
echo "[pico-motor-test] stopping ROS users of the Pico serial port"
pkill -f pico_bridge_node || true
pkill -f start_presentation_mode.sh || true
pkill -f start_mapping_panel.sh || true
sleep 1

run_wheel() {
  local wheel="$1"
  local speed="$2"
  local label="$3"
  echo
  echo "[pico-motor-test] ${wheel} ${label} for 0.6s"
  read -r -p "Watch which physical wheel moves, then press Enter..."
  mpremote connect "${PORT}" exec "import time; from motor_driver import motors; [m.stop() for m in motors.values()]; motors['${wheel}'].set_speed(${speed}); time.sleep(0.6); [m.stop() for m in motors.values()]"
  sleep 0.5
}

echo
echo "Write down, for each test, which physical wheel moved and whether + feels forward/clockwise for that wheel."
echo "Expected logical mapping is: left=m0/front-left, right=m1/front-right, back=m2/rear."

for wheel in left right back; do
  run_wheel "${wheel}" "0.32" "+speed"
  run_wheel "${wheel}" "-0.32" "-speed"
done

echo
echo "[pico-motor-test] resetting Pico back into firmware main.py"
mpremote connect "${PORT}" reset || true
echo "[pico-motor-test] done"
