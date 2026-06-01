#!/usr/bin/env bash
set -u

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

pass() {
  echo -e "${GREEN}[PASS]${NC} $1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
  WARN_COUNT=$((WARN_COUNT + 1))
}

fail() {
  echo -e "${RED}[FAIL]${NC} $1"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

section() {
  echo
  echo -e "${BLUE}== $1 ==${NC}"
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

source_if_exists() {
  local target="$1"
  if [[ -f "$target" ]]; then
    set +u
    # shellcheck disable=SC1090
    source "$target"
    set -u
  fi
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_DIR="$ROOT_DIR/software/pi5/ros2_ws"
source_if_exists "/opt/ros/jazzy/setup.bash"
source_if_exists "$WS_DIR/install/setup.bash"

section "ROS Nodes"
if ! have_cmd ros2; then
  fail "ros2 command not found"
else
  NODE_LIST="$(ros2 node list 2>/dev/null || true)"
  for node in /waypoint_manager_node /pico_bridge_node /command_mux_node /safety_supervisor_node /lidar_avoidance_node; do
    if grep -qx "$node" <<<"$NODE_LIST"; then
      pass "$node is running"
    else
      if [[ "$node" == "/pico_bridge_node" || "$node" == "/command_mux_node" ]]; then
        fail "$node is not running"
      else
        warn "$node is not running"
      fi
    fi
  done
fi

section "ROS Topics"
if have_cmd ros2; then
  TOPIC_LIST="$(ros2 topic list 2>/dev/null || true)"
  if grep -qx "/cmd_vel_final" <<<"$TOPIC_LIST"; then
    pass "/cmd_vel_final exists"
  else
    warn "/cmd_vel_final missing"
  fi
  if grep -qx "/nav/navigation_status" <<<"$TOPIC_LIST"; then
    pass "/nav/navigation_status exists"
  else
    warn "/nav/navigation_status missing"
  fi

  if grep -qx "/scan" <<<"$TOPIC_LIST"; then
    HZ_OUTPUT="$(timeout 8s ros2 topic hz /scan --window 5 2>/dev/null || true)"
    SCAN_HZ="$(grep -Eo '[0-9]+(\.[0-9]+)?' <<<"$HZ_OUTPUT" | tail -n 1)"
    if [[ -n "${SCAN_HZ:-}" ]]; then
      if awk "BEGIN {exit !($SCAN_HZ > 5.0)}"; then
        pass "/scan publishing at ${SCAN_HZ} Hz"
      else
        warn "/scan publishing slowly at ${SCAN_HZ} Hz"
      fi
    else
      warn "/scan exists but hz could not be measured"
    fi
  else
    warn "/scan topic missing"
  fi
fi

section "Panel API"
STATUS_JSON="$(curl -s --max-time 3 http://127.0.0.1:8090/api/status || true)"
if [[ -n "$STATUS_JSON" ]]; then
  pass "/api/status responded"
  if grep -q '"ros2_connected":[[:space:]]*true' <<<"$STATUS_JSON"; then
    pass "ros2_connected: true"
  else
    warn "ros2_connected is false"
  fi
  if grep -q '"pico_connected":[[:space:]]*true' <<<"$STATUS_JSON"; then
    pass "pico_connected: true"
  else
    fail "pico_connected is false"
  fi
else
  fail "/api/status did not return HTTP 200 within 3 seconds"
fi

section "Audio"
if have_cmd espeak-ng; then
  pass "espeak-ng found"
else
  warn "espeak-ng not installed"
fi
if have_cmd mpg123; then
  pass "mpg123 found for server Edge TTS playback"
else
  warn "mpg123 not installed; run: sudo apt install -y mpg123"
fi
if python3 -c "import faster_whisper" >/dev/null 2>&1; then
  pass "faster-whisper found for local wake-word and STT fallback"
else
  warn "faster-whisper not installed; run: bash scripts/setup_pi5_whisper.sh"
fi

section "USB Devices"
USB_OUTPUT="$(lsusb 2>/dev/null || true)"
if grep -qi "2148:7022" <<<"$USB_OUTPUT"; then
  pass "USB hub found"
else
  warn "USB hub 2148:7022 not found"
fi
if grep -qi "10c4:ea60" <<<"$USB_OUTPUT"; then
  pass "LiDAR CP210x found"
else
  warn "LiDAR CP210x not found"
fi
if grep -qi "2e8a:" <<<"$USB_OUTPUT"; then
  pass "Pico USB found"
else
  fail "Pico USB not found"
fi
if grep -qi "046d:08e5" <<<"$USB_OUTPUT"; then
  pass "Camera C920 found"
else
  warn "Camera C920 not found"
fi

echo
echo "------------------------------"
echo "Results: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL"
if [[ $FAIL_COUNT -gt 0 ]]; then
  echo "-> System NOT ready. Fix FAIL items first."
  exit 1
fi
echo "-> System ready enough for manual verification."
exit 0
