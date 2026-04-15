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

configure_offline_ros() {
  export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}"
  export ROS_LOCALHOST_ONLY=0
  unset ROS_DISCOVERY_SERVER
  unset ROS_SUPER_CLIENT
}

is_truthy() {
  case "${1:-0}" in
    1|[Tt][Rr][Uu][Ee]|[Yy][Ee][Ss]|[Oo][Nn]) return 0 ;;
    *) return 1 ;;
  esac
}

bool_param_value() {
  if is_truthy "${1:-0}"; then
    echo true
  else
    echo false
  fi
}

float_param_value() {
  local raw="${1:-0}"
  if [[ "$raw" =~ ^-?[0-9]+$ ]]; then
    echo "${raw}.0"
  else
    echo "$raw"
  fi
}

safe_source "/opt/ros/$ROS_DISTRO_NAME/setup.bash"
safe_source "$WS_DIR/install/setup.bash"
configure_offline_ros
ros2 daemon stop >/dev/null 2>&1 || true
ros2 daemon start >/dev/null 2>&1 || true
sleep 2
eval "$(python3 "$ROOT_DIR/scripts/probe_pi5_devices.py" --shell)"
PICO_PORT="${PICO_PORT:-${BUDDYBOT_PICO_PORT:-}}"
LIDAR_PORT="${LIDAR_PORT:-${BUDDYBOT_LIDAR_PORT:-}}"
CAMERA_DEVICE="${CAMERA_DEVICE:-${BUDDYBOT_CAMERA_DEVICE:-}}"
PANEL_BUILD="$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
export BUDDYBOT_PANEL_BUILD="${BUDDYBOT_PANEL_BUILD:-$PANEL_BUILD}"
export BUDDYBOT_PANEL_STATIC_DIR="${BUDDYBOT_PANEL_STATIC_DIR:-$ROOT_DIR/software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/static}"
export BUDDYBOT_WAYPOINT_FILE="${BUDDYBOT_WAYPOINT_FILE:-$ROOT_DIR/software/pi5/ros2_ws/src/buddybot_nav/config/waypoints.yaml}"

PIDS=()
LIDAR_STARTED=0
LIDAR_PID=""
LIDAR_RECOVERY_ATTEMPTED=0
CAMERA_START_DELAY="${BUDDYBOT_CAMERA_START_DELAY:-4}"
LIDAR_SETTLE_DELAY="${BUDDYBOT_LIDAR_SETTLE_DELAY:-6}"
CAMERA_WIDTH="${BUDDYBOT_CAMERA_WIDTH:-320}"
CAMERA_HEIGHT="${BUDDYBOT_CAMERA_HEIGHT:-240}"
CAMERA_FPS="$(float_param_value "${BUDDYBOT_CAMERA_FPS:-15.0}")"
CAMERA_PUBLISH_RATE="$(float_param_value "${BUDDYBOT_CAMERA_PUBLISH_RATE:-10.0}")"
CAMERA_PIXEL_FORMAT="${BUDDYBOT_CAMERA_PIXEL_FORMAT:-MJPG}"
CAMERA_BUFFER_SIZE="${BUDDYBOT_CAMERA_BUFFER_SIZE:-1}"
DETECT_INTERVAL="${BUDDYBOT_DETECT_INTERVAL:-5}"
DETECT_CONFIDENCE="$(float_param_value "${BUDDYBOT_DETECT_CONFIDENCE:-0.5}")"
DETECT_HOG_RESIZE_WIDTH="${BUDDYBOT_DETECT_HOG_RESIZE_WIDTH:-480}"
DETECT_ALLOW_HOG_FALLBACK="${BUDDYBOT_DETECT_ALLOW_HOG_FALLBACK:-1}"
DETECT_ALLOW_HOG_FALLBACK_PARAM="$(bool_param_value "$DETECT_ALLOW_HOG_FALLBACK")"
DISABLE_CAMERA="${BUDDYBOT_DISABLE_CAMERA:-0}"
DISABLE_PICO="${BUDDYBOT_DISABLE_PICO:-0}"
FORCE_LIDAR_START="${BUDDYBOT_FORCE_LIDAR_START:-0}"
ENABLE_OFFLINE_VOICE="${BUDDYBOT_ENABLE_OFFLINE_VOICE:-1}"
ENABLE_MIC_LISTENER="${BUDDYBOT_ENABLE_MIC_LISTENER:-${MIC_AVAILABLE:-0}}"
ENABLE_PI_SPEAKER="${BUDDYBOT_ENABLE_PI_SPEAKER:-1}"
VOICE_MIC_PARAM="$(bool_param_value "$ENABLE_MIC_LISTENER")"
VOICE_SPEAKER_PARAM="$(bool_param_value "$ENABLE_PI_SPEAKER")"

start_node() {
  local name="$1"
  shift
  local pid=""
  echo "[demo] starting $name"
  if [[ "$name" == "lidar" ]]; then
    nohup "$@" > "$LOG_DIR/$name.log" 2>&1 < /dev/null &
  else
    "$@" > "$LOG_DIR/$name.log" 2>&1 &
  fi
  pid="$!"
  PIDS+=("$pid")
  if [[ "$name" == "lidar" ]]; then
    LIDAR_PID="$pid"
  fi
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

wait_for_message() {
  local topic="$1"
  local timeout="${2:-8}"
  timeout "${timeout}s" ros2 topic echo --once "$topic" >/dev/null 2>&1
}

wait_for_scan_message() {
  local timeout="${1:-8}"
  timeout "${timeout}s" ros2 topic echo --qos-reliability best_effort --once /scan >/dev/null 2>&1 \
    || timeout "${timeout}s" ros2 topic echo --qos-reliability reliable --once /scan >/dev/null 2>&1
}

scan_streaming() {
  local timeout="${1:-8}"
  wait_for_scan_message "$timeout" || scan_available
}

camera_streaming() {
  local timeout="${1:-8}"
  wait_for_message "/camera/image_raw" "$timeout" || camera_available
}

pico_streaming() {
  local timeout="${1:-6}"
  wait_for_message "/buddybot/pico_status" "$timeout" \
    || ros2 topic list 2>/dev/null | grep -q '^/buddybot/pico_status$' \
    || ros2 node info /pico_bridge_node 2>/dev/null | grep -Eq '(^|[[:space:]])/?buddybot/pico_status([[:space:]]|$)'
}

read_throttled_state() {
  if command -v vcgencmd >/dev/null 2>&1; then
    vcgencmd get_throttled 2>/dev/null || true
  fi
}

report_camera_diagnostics() {
  local usb_camera=""
  local v4l_devices=""

  if command -v lsusb >/dev/null 2>&1; then
    usb_camera="$(lsusb | grep -Ei '046d|camera|webcam' || true)"
    if [[ -n "$usb_camera" ]]; then
      echo "[demo] usb camera entries:"
      while IFS= read -r line; do
        [[ -n "$line" ]] && echo "[demo]   $line"
      done <<< "$usb_camera"
    else
      echo "[demo] usb camera entries: none"
    fi
  fi

  if command -v v4l2-ctl >/dev/null 2>&1; then
    v4l_devices="$(v4l2-ctl --list-devices 2>/dev/null || true)"
    if [[ -n "$v4l_devices" ]]; then
      echo "[demo] v4l2 devices:"
      while IFS= read -r line; do
        [[ -n "$line" ]] && echo "[demo]   ${line//$'\t'/  }"
      done <<< "$(printf '%s\n' "$v4l_devices" | tail -n 16)"
    else
      echo "[demo] v4l2 devices: none"
    fi
  fi
}

report_power_diagnostics() {
  local throttled_line="unavailable"
  local throttled_hex=""
  local kernel_notes=""

  throttled_line="$(read_throttled_state)"
  if [[ "$throttled_line" =~ throttled=0x([0-9a-fA-F]+) ]]; then
    throttled_hex="${BASH_REMATCH[1]}"
  fi

  echo "[demo] power/throttle: ${throttled_line:-unavailable}"

  if [[ "${throttled_line,,}" == *"can't open device file"* ]] || [[ "${throttled_line,,}" == *"unavailable"* ]]; then
    echo "[demo] power status: vcgencmd unavailable on this image"
  else
    case "${throttled_hex,,}" in
      ""|"0")
        echo "[demo] power status: normal"
        ;;
      *)
        echo "[demo] warning: Pi reported throttle/undervoltage flags (0x${throttled_hex})"
        ;;
    esac
  fi

  if command -v journalctl >/dev/null 2>&1; then
    kernel_notes="$(journalctl -k -b 2>/dev/null | grep -Ei 'under-voltage|voltage|usb|disconnect|reset high-speed|descriptor read|over-current|enumerate|not enough power' | tail -n 5 || true)"
    if [[ -n "$kernel_notes" ]]; then
      echo "[demo] recent kernel power/USB notes:"
      while IFS= read -r line; do
        [[ -n "$line" ]] && echo "[demo]   $line"
      done <<< "$kernel_notes"
    else
      echo "[demo] recent kernel power/USB notes: none"
    fi
  fi
}

stop_lidar_node() {
  if [[ -n "$LIDAR_PID" ]] && kill -0 "$LIDAR_PID" 2>/dev/null; then
    kill "$LIDAR_PID" 2>/dev/null || true
    wait "$LIDAR_PID" 2>/dev/null || true
  fi
  LIDAR_PID=""
  LIDAR_STARTED=0
}

start_lidar_if_available() {
  local serial_port="${BUDDYBOT_LIDAR_PORT:-${LIDAR_PORT:-}}"
  local serial_baudrate="${BUDDYBOT_LIDAR_BAUDRATE:-115200}"
  local pkg_prefix=""
  local pkg_share=""
  local launch_file=""

  if ! is_truthy "$FORCE_LIDAR_START" && scan_available; then
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

ensure_lidar_stream() {
  local reason="$1"
  if scan_streaming 8; then
    return 0
  fi

  echo "[demo] warning: /scan is not receiving live messages after $reason"
  if [[ "$LIDAR_STARTED" -ne 1 ]]; then
    echo "[demo] check: tail -n 120 $LOG_DIR/lidar.log"
    return 1
  fi

  if [[ "$LIDAR_RECOVERY_ATTEMPTED" -eq 1 ]]; then
    echo "[demo] warning: LiDAR recovery already attempted once"
    echo "[demo] check: tail -n 120 $LOG_DIR/lidar.log"
    return 1
  fi

  LIDAR_RECOVERY_ATTEMPTED=1
  echo "[demo] restarting lidar after $reason"
  stop_lidar_node
  sleep 2
  start_lidar_if_available
  if scan_streaming 10; then
    echo "[demo] lidar scan recovered"
    return 0
  fi

  echo "[demo] warning: /scan is still missing after lidar restart"
  echo "[demo] check: tail -n 120 $LOG_DIR/lidar.log"
  return 1
}

echo "[demo] detected Pico port: ${PICO_PORT:-none}"
echo "[demo] detected LiDAR port: ${LIDAR_PORT:-none}"
echo "[demo] detected camera device: ${CAMERA_DEVICE:-none}"
echo "[demo] microphone available: ${MIC_AVAILABLE:-0}"
echo "[demo] AI server: ${AI_SERVER_STATE:-unknown}"
echo "[demo] lidar settle delay: ${LIDAR_SETTLE_DELAY}s"
echo "[demo] camera start delay: ${CAMERA_START_DELAY}s"
echo "[demo] camera profile: ${CAMERA_WIDTH}x${CAMERA_HEIGHT} @ ${CAMERA_FPS}fps publish ${CAMERA_PUBLISH_RATE}Hz"
echo "[demo] camera pixel format: ${CAMERA_PIXEL_FORMAT} buffer ${CAMERA_BUFFER_SIZE}"
echo "[demo] detector profile: interval ${DETECT_INTERVAL}, confidence ${DETECT_CONFIDENCE}, hog resize ${DETECT_HOG_RESIZE_WIDTH}, hog fallback ${DETECT_ALLOW_HOG_FALLBACK_PARAM}"
echo "[demo] camera disabled: ${DISABLE_CAMERA}"
echo "[demo] pico disabled: ${DISABLE_PICO}"
echo "[demo] force lidar start: ${FORCE_LIDAR_START}"
echo "[demo] offline voice enabled: ${ENABLE_OFFLINE_VOICE}"
echo "[demo] microphone listener enabled: ${ENABLE_MIC_LISTENER}"
echo "[demo] Pi speaker enabled: ${ENABLE_PI_SPEAKER}"
echo "[demo] panel build: ${BUDDYBOT_PANEL_BUILD}"
echo "[demo] ROS_DOMAIN_ID: ${ROS_DOMAIN_ID}"
echo "[demo] ROS_LOCALHOST_ONLY: ${ROS_LOCALHOST_ONLY}"
echo "[demo] ROS_DISCOVERY_SERVER: ${ROS_DISCOVERY_SERVER:-unset}"
if [[ -z "${PICO_PORT:-}" ]]; then
  echo "[demo] serial candidates: ${SERIAL_CANDIDATES:-none}"
  echo "[demo] serial by-id: ${SERIAL_BY_ID:-none}"
  if command -v lsusb >/dev/null 2>&1; then
    PICO_USB_HINTS="$(lsusb | grep -Ei '2e8a|raspberry pi pico|micropython|rp2' || true)"
    echo "[demo] pico usb hints: ${PICO_USB_HINTS:-none}"
  fi
fi
report_power_diagnostics
report_camera_diagnostics

start_lidar_if_available
if [[ "$LIDAR_STARTED" -eq 1 ]]; then
  pause_before_node "$LIDAR_SETTLE_DELAY" "starting camera after lidar spin-up"
  ensure_lidar_stream "initial lidar startup" || true
fi
if is_truthy "$DISABLE_PICO"; then
  echo "[demo] pico bridge disabled by BUDDYBOT_DISABLE_PICO=1"
else
  if [[ -n "${PICO_PORT:-}" ]]; then
    start_node pico_bridge ros2 run buddybot_base pico_bridge_node --ros-args -p serial_port:="${PICO_PORT}"
  else
    start_node pico_bridge ros2 run buddybot_base pico_bridge_node
  fi
  if pico_streaming 6; then
    echo "[demo] pico status is live"
  else
    echo "[demo] warning: /buddybot/pico_status is not being published yet"
    echo "[demo] check: tail -n 120 $LOG_DIR/pico_bridge.log"
    echo "[demo] tip: if the port shows MicroPython but no status arrives, reflash Pico with bash scripts/flash_pico.sh"
  fi
fi
start_node command_mux ros2 run buddybot_system command_mux_node
start_node mode_manager ros2 run buddybot_system mode_manager_node
start_node safety_supervisor ros2 run buddybot_system safety_supervisor_node
start_node lidar_avoidance ros2 run buddybot_system lidar_avoidance_node
if is_truthy "$ENABLE_OFFLINE_VOICE"; then
  start_node voice ros2 run buddybot_voice voice_interface --ros-args -p offline_mode:=true -p enable_microphone:="${VOICE_MIC_PARAM}" -p enable_speaker_output:="${VOICE_SPEAKER_PARAM}"
fi
if is_truthy "$DISABLE_CAMERA"; then
  echo "[demo] camera pipeline disabled by BUDDYBOT_DISABLE_CAMERA=1"
else
  pause_before_node "$CAMERA_START_DELAY" "starting camera"
  if [[ -n "${CAMERA_DEVICE:-}" ]]; then
    start_node camera ros2 run buddybot_vision camera_node --ros-args -p device:="${CAMERA_DEVICE}" -p width:="${CAMERA_WIDTH}" -p height:="${CAMERA_HEIGHT}" -p fps:="${CAMERA_FPS}" -p publish_rate:="${CAMERA_PUBLISH_RATE}" -p pixel_format:="${CAMERA_PIXEL_FORMAT}" -p buffer_size:="${CAMERA_BUFFER_SIZE}"
  else
    echo "[demo] warning: probe did not find a preferred camera device; trying auto detection"
    start_node camera ros2 run buddybot_vision camera_node --ros-args -p width:="${CAMERA_WIDTH}" -p height:="${CAMERA_HEIGHT}" -p fps:="${CAMERA_FPS}" -p publish_rate:="${CAMERA_PUBLISH_RATE}" -p pixel_format:="${CAMERA_PIXEL_FORMAT}" -p buffer_size:="${CAMERA_BUFFER_SIZE}"
  fi
  if camera_streaming 8; then
    echo "[demo] camera stream is live"
    start_node detector ros2 run buddybot_vision detector_node --ros-args -p detection_interval:="${DETECT_INTERVAL}" -p confidence_threshold:="${DETECT_CONFIDENCE}" -p hog_resize_width:="${DETECT_HOG_RESIZE_WIDTH}" -p allow_hog_fallback:="${DETECT_ALLOW_HOG_FALLBACK_PARAM}"
    start_node follow_controller ros2 run buddybot_vision follow_controller_node --ros-args -p image_width:="${CAMERA_WIDTH}" -p image_height:="${CAMERA_HEIGHT}"
  else
    echo "[demo] warning: /camera/image_raw is not being published yet"
    echo "[demo] detector/follow startup skipped until camera is fixed"
    echo "[demo] check: tail -n 120 $LOG_DIR/camera.log"
    echo "[demo] tip: if C920 is missing from lsusb/v4l2 above, this is likely USB/power rather than ROS"
  fi
  ensure_lidar_stream "camera startup" || true
fi
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

if ! scan_streaming 8; then
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
