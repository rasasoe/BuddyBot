#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WS_DIR="$ROOT_DIR/software/pi5/ros2_ws"
LOG_DIR="$WS_DIR/log/mapping_panel"
ROS_DISTRO_NAME="${ROS_DISTRO:-jazzy}"

mkdir -p "$LOG_DIR"

if [[ ! -f "/opt/ros/$ROS_DISTRO_NAME/setup.bash" ]]; then
  echo "[mapping] error: /opt/ros/$ROS_DISTRO_NAME/setup.bash not found"
  exit 1
fi

if [[ ! -f "$WS_DIR/install/setup.bash" ]]; then
  echo "[mapping] error: workspace is not built yet"
  echo "[mapping] run: bash $ROOT_DIR/scripts/setup_pi5.sh"
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
LIDAR_STARTED_BAUDRATE=""
LIDAR_RECOVERY_ATTEMPTED=0
LIDAR_STREAM_CONFIRMED=0
CAMERA_START_DELAY="${BUDDYBOT_CAMERA_START_DELAY:-10}"
LIDAR_SETTLE_DELAY="${BUDDYBOT_LIDAR_SETTLE_DELAY:-10}"
CAMERA_WIDTH="${BUDDYBOT_CAMERA_WIDTH:-320}"
CAMERA_HEIGHT="${BUDDYBOT_CAMERA_HEIGHT:-240}"
CAMERA_FPS="$(float_param_value "${BUDDYBOT_CAMERA_FPS:-15.0}")"
CAMERA_PUBLISH_RATE="$(float_param_value "${BUDDYBOT_CAMERA_PUBLISH_RATE:-15.0}")"
CAMERA_PIXEL_FORMAT="${BUDDYBOT_CAMERA_PIXEL_FORMAT:-MJPG}"
CAMERA_BUFFER_SIZE="${BUDDYBOT_CAMERA_BUFFER_SIZE:-1}"
CAMERA_DISCARD_BUFFERED_FRAMES="${BUDDYBOT_CAMERA_DISCARD_BUFFERED_FRAMES:-1}"
CAMERA_OPENCV_THREADS="${BUDDYBOT_CAMERA_OPENCV_THREADS:-2}"
DETECT_INTERVAL="${BUDDYBOT_DETECT_INTERVAL:-2}"
DETECT_CONFIDENCE="$(float_param_value "${BUDDYBOT_DETECT_CONFIDENCE:-0.2}")"
DETECT_OPENCV_THREADS="${BUDDYBOT_DETECT_OPENCV_THREADS:-2}"
DETECT_HOG_CONFIDENCE="$(float_param_value "${BUDDYBOT_DETECT_HOG_CONFIDENCE:-0.08}")"
DETECT_HOG_RESIZE_WIDTH="${BUDDYBOT_DETECT_HOG_RESIZE_WIDTH:-320}"
DETECT_ALLOW_HOG_FALLBACK="${BUDDYBOT_DETECT_ALLOW_HOG_FALLBACK:-1}"
DETECT_ALLOW_HOG_FALLBACK_PARAM="$(bool_param_value "$DETECT_ALLOW_HOG_FALLBACK")"
DETECT_ALLOW_CASCADE_FALLBACK="${BUDDYBOT_DETECT_ALLOW_CASCADE_FALLBACK:-1}"
DETECT_ALLOW_CASCADE_FALLBACK_PARAM="$(bool_param_value "$DETECT_ALLOW_CASCADE_FALLBACK")"
DETECT_PUBLISH_DEBUG_IMAGE_PARAM="$(bool_param_value "${BUDDYBOT_DETECT_PUBLISH_DEBUG:-1}")"
FOLLOW_BBOX_TIMEOUT="$(float_param_value "${BUDDYBOT_FOLLOW_BBOX_TIMEOUT:-2.5}")"
FOLLOW_MAX_SOURCE_AGE="$(float_param_value "${BUDDYBOT_FOLLOW_MAX_SOURCE_AGE:-0.0}")"
FOLLOW_HEIGHT_GAIN="$(float_param_value "${BUDDYBOT_FOLLOW_HEIGHT_GAIN:-0.010}")"
FOLLOW_CENTER_GAIN="$(float_param_value "${BUDDYBOT_FOLLOW_CENTER_GAIN:-0.00055}")"
FOLLOW_TARGET_HEIGHT="$(float_param_value "${BUDDYBOT_FOLLOW_TARGET_HEIGHT:-1.16}")"
FOLLOW_MAX_LINEAR="$(float_param_value "${BUDDYBOT_FOLLOW_MAX_LINEAR:-0.42}")"
FOLLOW_MAX_ANGULAR="$(float_param_value "${BUDDYBOT_FOLLOW_MAX_ANGULAR:-0.045}")"
FOLLOW_MIN_LINEAR="$(float_param_value "${BUDDYBOT_FOLLOW_MIN_LINEAR:-0.34}")"
FOLLOW_COMMAND_RATE="$(float_param_value "${BUDDYBOT_FOLLOW_COMMAND_RATE:-10.0}")"
FOLLOW_LINEAR_ACCEL="$(float_param_value "${BUDDYBOT_FOLLOW_LINEAR_ACCEL:-0.55}")"
FOLLOW_ANGULAR_ACCEL="$(float_param_value "${BUDDYBOT_FOLLOW_ANGULAR_ACCEL:-0.05}")"
FOLLOW_BBOX_SMOOTHING_ALPHA="$(float_param_value "${BUDDYBOT_FOLLOW_BBOX_SMOOTHING_ALPHA:-0.45}")"
FOLLOW_BBOX_FILTER_RESET_SEC="$(float_param_value "${BUDDYBOT_FOLLOW_BBOX_FILTER_RESET_SEC:-0.9}")"
FOLLOW_CENTER_DEADZONE="${BUDDYBOT_FOLLOW_CENTER_DEADZONE:-50}"
FOLLOW_HEIGHT_DEADZONE="${BUDDYBOT_FOLLOW_HEIGHT_DEADZONE:-16}"
FOLLOW_ALLOW_REVERSE_PARAM="$(bool_param_value "${BUDDYBOT_FOLLOW_ALLOW_REVERSE:-0}")"
FOLLOW_VISIBLE_FORWARD="$(float_param_value "${BUDDYBOT_FOLLOW_VISIBLE_FORWARD:-0.34}")"
FOLLOW_VISIBLE_FORWARD_CENTER_DEADZONE="${BUDDYBOT_FOLLOW_VISIBLE_FORWARD_CENTER_DEADZONE:-120}"
FOLLOW_VISIBLE_FORWARD_MAX_HEIGHT="$(float_param_value "${BUDDYBOT_FOLLOW_VISIBLE_FORWARD_MAX_HEIGHT:-1.10}")"
FOLLOW_FORWARD_YAW_TRIM="$(float_param_value "${BUDDYBOT_FOLLOW_FORWARD_YAW_TRIM:--0.05}")"
FOLLOW_FORWARD_YAW_TRIM_CENTER_DEADZONE="${BUDDYBOT_FOLLOW_FORWARD_YAW_TRIM_CENTER_DEADZONE:-120}"
FOLLOW_NEAR_TURN_AREA="$(float_param_value "${BUDDYBOT_FOLLOW_NEAR_TURN_AREA:-0.34}")"
FOLLOW_NEAR_TURN_WIDTH="$(float_param_value "${BUDDYBOT_FOLLOW_NEAR_TURN_WIDTH:-0.50}")"
FOLLOW_CLOSE_STOP_AREA="$(float_param_value "${BUDDYBOT_FOLLOW_CLOSE_STOP_AREA:-0.56}")"
FOLLOW_CLOSE_STOP_WIDTH="$(float_param_value "${BUDDYBOT_FOLLOW_CLOSE_STOP_WIDTH:-0.70}")"
FOLLOW_CLOSE_STOP_TOP="$(float_param_value "${BUDDYBOT_FOLLOW_CLOSE_STOP_TOP:-0.05}")"
FOLLOW_CLOSE_STOP_MIN_HEIGHT="$(float_param_value "${BUDDYBOT_FOLLOW_CLOSE_STOP_MIN_HEIGHT:-0.90}")"
FOLLOW_USE_LIDAR_DISTANCE_PARAM="$(bool_param_value "${BUDDYBOT_FOLLOW_USE_LIDAR_DISTANCE:-0}")"
FOLLOW_TARGET_DISTANCE="$(float_param_value "${BUDDYBOT_FOLLOW_TARGET_DISTANCE:-0.95}")"
FOLLOW_DISTANCE_DEADZONE="$(float_param_value "${BUDDYBOT_FOLLOW_DISTANCE_DEADZONE:-0.18}")"
FOLLOW_MIN_DISTANCE="$(float_param_value "${BUDDYBOT_FOLLOW_MIN_DISTANCE:-0.45}")"
FOLLOW_LIDAR_GAIN="$(float_param_value "${BUDDYBOT_FOLLOW_LIDAR_GAIN:-0.24}")"
FOLLOW_LIDAR_SECTOR="$(float_param_value "${BUDDYBOT_FOLLOW_LIDAR_SECTOR:-18}")"
DISABLE_CAMERA="${BUDDYBOT_DISABLE_CAMERA:-0}"
DISABLE_PICO="${BUDDYBOT_DISABLE_PICO:-0}"
FORCE_LIDAR_START="${BUDDYBOT_FORCE_LIDAR_START:-0}"
ENABLE_OFFLINE_VOICE="${BUDDYBOT_ENABLE_OFFLINE_VOICE:-1}"
ENABLE_MIC_LISTENER="${BUDDYBOT_ENABLE_MIC_LISTENER:-${MIC_AVAILABLE:-0}}"
ENABLE_PI_SPEAKER="${BUDDYBOT_ENABLE_PI_SPEAKER:-1}"
SPEAKER_VOLUME_PERCENT="${BUDDYBOT_SPEAKER_VOLUME_PERCENT:-60}"
VOICE_COMMAND_ENABLED_PARAM="$(bool_param_value "${BUDDYBOT_VOICE_COMMAND_ENABLED:-1}")"
VOICE_AI_URL="${BUDDYBOT_AI_URL:-http://100.115.246.76:8000}"
VOICE_RECOGNITION_BACKEND="${BUDDYBOT_VOICE_RECOGNITION_BACKEND:-google}"
VOICE_ALLOW_ONLINE_RECOGNITION_PARAM="$(bool_param_value "${BUDDYBOT_VOICE_ALLOW_ONLINE_RECOGNITION:-1}")"
VOICE_RECOGNITION_LANGUAGE="${BUDDYBOT_VOICE_RECOGNITION_LANGUAGE:-ko-KR}"
VOICE_PHRASE_TIME_LIMIT="${BUDDYBOT_VOICE_PHRASE_TIME_LIMIT:-2.6}"
VOICE_MOVING_PHRASE_TIME_LIMIT="${BUDDYBOT_VOICE_MOVING_PHRASE_TIME_LIMIT:-1.2}"
VOICE_WAKE_TIMEOUT="${BUDDYBOT_VOICE_WAKE_TIMEOUT:-10.0}"
VOICE_PAUSE_THRESHOLD="${BUDDYBOT_VOICE_PAUSE_THRESHOLD:-0.45}"
VOICE_NON_SPEAKING_DURATION="${BUDDYBOT_VOICE_NON_SPEAKING_DURATION:-0.25}"
VOICE_GOOGLE_TIMEOUT_SEC="${BUDDYBOT_VOICE_GOOGLE_TIMEOUT_SEC:-1.8}"
VOICE_MANUAL_SPEED="${BUDDYBOT_VOICE_MANUAL_SPEED:-0.44}"
VOICE_MANUAL_TIMEOUT_SEC="${BUDDYBOT_VOICE_MANUAL_TIMEOUT_SEC:-2.0}"
VOICE_SPEAKER_RATE_WPM="${BUDDYBOT_VOICE_SPEAKER_RATE_WPM:-180}"
VOICE_SPEAK_COMMAND_RESPONSES_PARAM="$(bool_param_value "${BUDDYBOT_VOICE_SPEAK_COMMAND_RESPONSES:-0}")"
VOICE_MIC_PARAM="$(bool_param_value "$ENABLE_MIC_LISTENER")"
VOICE_SPEAKER_PARAM="$(bool_param_value "$ENABLE_PI_SPEAKER")"
COMMAND_TIMEOUT="$(float_param_value "${BUDDYBOT_COMMAND_TIMEOUT:-1.2}")"

start_node() {
  local name="$1"
  shift
  local pid=""
  echo "[mapping] starting $name"
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
    echo "[mapping] waiting ${seconds}s before $reason"
    sleep "$seconds"
  fi
}

cleanup() {
  echo
  echo "[mapping] stopping nodes"
  if declare -F stop_lidar_node >/dev/null 2>&1; then
    stop_lidar_node
  fi
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

wait_for_best_effort_message() {
  local topic="$1"
  local timeout="${2:-8}"
  timeout "${timeout}s" ros2 topic echo --qos-reliability best_effort --once "$topic" >/dev/null 2>&1 \
    || timeout "${timeout}s" ros2 topic echo --qos-reliability reliable --once "$topic" >/dev/null 2>&1
}

scan_streaming() {
  local timeout="${1:-8}"
  wait_for_best_effort_message "/scan" "$timeout"
}

camera_streaming() {
  local timeout="${1:-8}"
  wait_for_best_effort_message "/camera/image_raw" "$timeout" || camera_available
}

set_speaker_volume() {
  local volume="${1:-35}"

  if ! is_truthy "$ENABLE_PI_SPEAKER"; then
    return 0
  fi

  if command -v wpctl >/dev/null 2>&1; then
    if wpctl set-volume @DEFAULT_AUDIO_SINK@ "${volume}%" >/dev/null 2>&1; then
      echo "[mapping] Pi speaker volume set to ${volume}% via wpctl"
      return 0
    fi
  fi

  if command -v pactl >/dev/null 2>&1; then
    if pactl set-sink-volume @DEFAULT_SINK@ "${volume}%" >/dev/null 2>&1; then
      echo "[mapping] Pi speaker volume set to ${volume}% via pactl"
      return 0
    fi
  fi

  if command -v amixer >/dev/null 2>&1; then
    if amixer -q sset Master "${volume}%" >/dev/null 2>&1; then
      echo "[mapping] Pi speaker volume set to ${volume}% via amixer"
      return 0
    fi
  fi

  echo "[mapping] warning: could not clamp Pi speaker volume to ${volume}%"
}

stop_stale_lidar_processes() {
  pkill -TERM -f "ros2 launch sllidar_ros2" >/dev/null 2>&1 || true
  pkill -TERM -f "sllidar_node" >/dev/null 2>&1 || true
}

stop_lidar_node() {
  if [[ -n "$LIDAR_PID" ]] && kill -0 "$LIDAR_PID" 2>/dev/null; then
    kill "$LIDAR_PID" 2>/dev/null || true
    wait "$LIDAR_PID" 2>/dev/null || true
  fi
  stop_stale_lidar_processes
  LIDAR_PID=""
  LIDAR_STARTED=0
  LIDAR_STARTED_BAUDRATE=""
}

show_lidar_log_tail() {
  if [[ -s "$LOG_DIR/lidar.log" ]]; then
    echo "[mapping] lidar.log tail:"
    tail -n 80 "$LOG_DIR/lidar.log" | sed 's/^/[lidar] /'
  fi
}

start_lidar_if_available() {
  local serial_port="${BUDDYBOT_LIDAR_PORT:-${LIDAR_PORT:-}}"
  local serial_baudrate="${1:-${BUDDYBOT_LIDAR_BAUDRATE:-115200}}"
  local pkg_prefix=""
  local pkg_share=""
  local launch_file=""

  if ! is_truthy "$FORCE_LIDAR_START" && scan_available; then
    echo "[mapping] lidar scan already available"
    return
  fi

  if ! pkg_prefix="$(ros2 pkg prefix sllidar_ros2 2>/dev/null)"; then
    echo "[mapping] lidar autostart skipped: sllidar_ros2 is not installed"
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
    echo "[mapping] lidar autostart skipped: no serial device found"
    return
  fi

  for candidate in sllidar_a1_launch.py view_sllidar_a1_launch.py sllidar_launch.py view_sllidar_launch.py; do
    if [[ -f "$pkg_share/launch/$candidate" ]]; then
      launch_file="$candidate"
      break
    fi
  done

  if [[ -z "$launch_file" ]]; then
    echo "[mapping] lidar autostart skipped: no known sllidar launch file found"
    return
  fi

  stop_stale_lidar_processes
  sleep 1
  start_node lidar ros2 launch sllidar_ros2 "$launch_file" serial_port:="$serial_port" serial_baudrate:="$serial_baudrate"
  LIDAR_STARTED=1
  LIDAR_STARTED_BAUDRATE="$serial_baudrate"
}

ensure_lidar_stream() {
  local reason="$1"
  if scan_streaming 8; then
    LIDAR_STREAM_CONFIRMED=1
    return 0
  fi

  echo "[mapping] warning: /scan is not receiving live messages after $reason"
  if [[ "$LIDAR_STARTED" -ne 1 ]]; then
    echo "[mapping] check: tail -n 120 $LOG_DIR/lidar.log"
    show_lidar_log_tail
    return 1
  fi

  if [[ "$LIDAR_RECOVERY_ATTEMPTED" -eq 1 ]]; then
    echo "[mapping] warning: LiDAR recovery already attempted once"
    echo "[mapping] check: tail -n 120 $LOG_DIR/lidar.log"
    show_lidar_log_tail
    return 1
  fi

  LIDAR_RECOVERY_ATTEMPTED=1
  echo "[mapping] restarting lidar after $reason"
  stop_lidar_node
  sleep 2
  start_lidar_if_available
  if scan_streaming 10; then
    echo "[mapping] lidar scan recovered"
    LIDAR_STREAM_CONFIRMED=1
    return 0
  fi

  if [[ -z "${BUDDYBOT_LIDAR_BAUDRATE:-}" ]]; then
    for alt_baudrate in 256000 115200; do
      if [[ "$alt_baudrate" == "$LIDAR_STARTED_BAUDRATE" ]]; then
        continue
      fi
      echo "[mapping] trying lidar baud ${alt_baudrate}"
      stop_lidar_node
      sleep 2
      start_lidar_if_available "$alt_baudrate"
      if scan_streaming 10; then
        echo "[mapping] lidar scan recovered at baud ${alt_baudrate}"
        LIDAR_STREAM_CONFIRMED=1
        return 0
      fi
    done
  fi

  echo "[mapping] warning: /scan is still missing after lidar restart"
  echo "[mapping] check: tail -n 120 $LOG_DIR/lidar.log"
  show_lidar_log_tail
  return 1
}

echo "[mapping] detected Pico port: ${PICO_PORT:-none}"
echo "[mapping] detected LiDAR port: ${LIDAR_PORT:-none}"
echo "[mapping] detected camera device: ${CAMERA_DEVICE:-none}"
echo "[mapping] microphone available: ${MIC_AVAILABLE:-0}"
echo "[mapping] AI server: ${AI_SERVER_STATE:-unknown}"
echo "[mapping] lidar settle delay: ${LIDAR_SETTLE_DELAY}s"
echo "[mapping] camera start delay: ${CAMERA_START_DELAY}s"
echo "[mapping] camera profile: ${CAMERA_WIDTH}x${CAMERA_HEIGHT} @ ${CAMERA_FPS}fps publish ${CAMERA_PUBLISH_RATE}Hz"
echo "[mapping] camera pixel format: ${CAMERA_PIXEL_FORMAT} buffer ${CAMERA_BUFFER_SIZE} discard_buffered ${CAMERA_DISCARD_BUFFERED_FRAMES} opencv_threads ${CAMERA_OPENCV_THREADS}"
echo "[mapping] detector profile: interval ${DETECT_INTERVAL}, confidence ${DETECT_CONFIDENCE}, hog confidence ${DETECT_HOG_CONFIDENCE}, hog resize ${DETECT_HOG_RESIZE_WIDTH}, hog fallback ${DETECT_ALLOW_HOG_FALLBACK_PARAM}, cascade fallback ${DETECT_ALLOW_CASCADE_FALLBACK_PARAM}, opencv_threads ${DETECT_OPENCV_THREADS}"
echo "[mapping] follow profile: bbox_timeout ${FOLLOW_BBOX_TIMEOUT}s max_source_age ${FOLLOW_MAX_SOURCE_AGE}s max_linear ${FOLLOW_MAX_LINEAR} max_angular ${FOLLOW_MAX_ANGULAR} accel ${FOLLOW_LINEAR_ACCEL}/${FOLLOW_ANGULAR_ACCEL} allow_reverse ${FOLLOW_ALLOW_REVERSE_PARAM} visible_forward ${FOLLOW_VISIBLE_FORWARD}@${FOLLOW_VISIBLE_FORWARD_CENTER_DEADZONE}px max_h ${FOLLOW_VISIBLE_FORWARD_MAX_HEIGHT} yaw_trim ${FOLLOW_FORWARD_YAW_TRIM}@${FOLLOW_FORWARD_YAW_TRIM_CENTER_DEADZONE}px near_turn ${FOLLOW_NEAR_TURN_AREA}/${FOLLOW_NEAR_TURN_WIDTH} close_stop ${FOLLOW_CLOSE_STOP_AREA}/${FOLLOW_CLOSE_STOP_WIDTH}/${FOLLOW_CLOSE_STOP_TOP} lidar_distance ${FOLLOW_USE_LIDAR_DISTANCE_PARAM} target ${FOLLOW_TARGET_DISTANCE}m"
echo "[mapping] camera disabled: ${DISABLE_CAMERA}"
echo "[mapping] pico disabled: ${DISABLE_PICO}"
echo "[mapping] force lidar start: ${FORCE_LIDAR_START}"
echo "[mapping] offline voice enabled: ${ENABLE_OFFLINE_VOICE}"
echo "[mapping] microphone listener enabled: ${ENABLE_MIC_LISTENER}"
echo "[mapping] voice recognition: backend ${VOICE_RECOGNITION_BACKEND}, online ${VOICE_ALLOW_ONLINE_RECOGNITION_PARAM}, language ${VOICE_RECOGNITION_LANGUAGE}, phrase ${VOICE_PHRASE_TIME_LIMIT}s moving_phrase ${VOICE_MOVING_PHRASE_TIME_LIMIT}s pause ${VOICE_PAUSE_THRESHOLD}s google_timeout ${VOICE_GOOGLE_TIMEOUT_SEC}s wake ${VOICE_WAKE_TIMEOUT}s manual_speed ${VOICE_MANUAL_SPEED} manual_timeout ${VOICE_MANUAL_TIMEOUT_SEC}s tts_rate ${VOICE_SPEAKER_RATE_WPM} command_speech ${VOICE_SPEAK_COMMAND_RESPONSES_PARAM}"
echo "[mapping] command mux timeout: ${COMMAND_TIMEOUT}s"
if [[ "$VOICE_RECOGNITION_BACKEND" == "google" || "$VOICE_RECOGNITION_BACKEND" == "auto" ]]; then
  if ! command -v flac >/dev/null 2>&1; then
    echo "[mapping] warning: google voice recognition needs flac; install with: sudo apt install -y flac"
  fi
fi
echo "[mapping] Pi speaker enabled: ${ENABLE_PI_SPEAKER}"
echo "[mapping] Pi speaker volume target: ${SPEAKER_VOLUME_PERCENT}%"
echo "[mapping] panel build: ${BUDDYBOT_PANEL_BUILD}"
echo "[mapping] ROS_DOMAIN_ID: ${ROS_DOMAIN_ID}"
echo "[mapping] ROS_LOCALHOST_ONLY: ${ROS_LOCALHOST_ONLY}"
echo "[mapping] ROS_DISCOVERY_SERVER: ${ROS_DISCOVERY_SERVER:-unset}"

start_lidar_if_available
if [[ "$LIDAR_STARTED" -eq 1 ]]; then
  pause_before_node "$LIDAR_SETTLE_DELAY" "starting camera after lidar spin-up"
  ensure_lidar_stream "initial lidar startup" || true
fi
if is_truthy "$DISABLE_PICO"; then
  echo "[mapping] pico bridge disabled by BUDDYBOT_DISABLE_PICO=1"
else
  if [[ -n "${PICO_PORT:-}" ]]; then
    start_node pico_bridge ros2 run buddybot_base pico_bridge_node --ros-args -p serial_port:="${PICO_PORT}"
  else
    start_node pico_bridge ros2 run buddybot_base pico_bridge_node
  fi
fi
start_node encoder_odom ros2 run buddybot_base encoder_odom_node
start_node command_mux ros2 run buddybot_system command_mux_node --ros-args -p command_timeout:="${COMMAND_TIMEOUT}"
start_node mode_manager ros2 run buddybot_system mode_manager_node
start_node safety_supervisor ros2 run buddybot_system safety_supervisor_node
start_node lidar_avoidance ros2 run buddybot_system lidar_avoidance_node
if is_truthy "$ENABLE_OFFLINE_VOICE"; then
  set_speaker_volume "$SPEAKER_VOLUME_PERCENT"
  start_node voice ros2 run buddybot_voice voice_interface --ros-args -p offline_mode:=true -p command_enabled:="${VOICE_COMMAND_ENABLED_PARAM}" -p buddybot_ai_url:="${VOICE_AI_URL}" -p enable_microphone:="${VOICE_MIC_PARAM}" -p enable_speaker_output:="${VOICE_SPEAKER_PARAM}" -p recognition_backend:="${VOICE_RECOGNITION_BACKEND}" -p allow_online_recognition:="${VOICE_ALLOW_ONLINE_RECOGNITION_PARAM}" -p recognition_language:="${VOICE_RECOGNITION_LANGUAGE}" -p phrase_time_limit:="${VOICE_PHRASE_TIME_LIMIT}" -p moving_phrase_time_limit:="${VOICE_MOVING_PHRASE_TIME_LIMIT}" -p wake_timeout_sec:="${VOICE_WAKE_TIMEOUT}" -p pause_threshold:="${VOICE_PAUSE_THRESHOLD}" -p non_speaking_duration:="${VOICE_NON_SPEAKING_DURATION}" -p google_timeout_sec:="${VOICE_GOOGLE_TIMEOUT_SEC}" -p manual_speed:="${VOICE_MANUAL_SPEED}" -p manual_command_timeout_sec:="${VOICE_MANUAL_TIMEOUT_SEC}" -p speaker_rate_wpm:="${VOICE_SPEAKER_RATE_WPM}" -p speak_command_responses:="${VOICE_SPEAK_COMMAND_RESPONSES_PARAM}"
fi
if is_truthy "$DISABLE_CAMERA"; then
  echo "[mapping] camera pipeline disabled by BUDDYBOT_DISABLE_CAMERA=1"
else
  pause_before_node "$CAMERA_START_DELAY" "starting camera"
  if [[ -n "${CAMERA_DEVICE:-}" ]]; then
    start_node camera ros2 run buddybot_vision camera_node --ros-args -p device:="${CAMERA_DEVICE}" -p width:="${CAMERA_WIDTH}" -p height:="${CAMERA_HEIGHT}" -p fps:="${CAMERA_FPS}" -p publish_rate:="${CAMERA_PUBLISH_RATE}" -p pixel_format:="${CAMERA_PIXEL_FORMAT}" -p buffer_size:="${CAMERA_BUFFER_SIZE}" -p discard_buffered_frames:="${CAMERA_DISCARD_BUFFERED_FRAMES}" -p opencv_threads:="${CAMERA_OPENCV_THREADS}"
  else
    start_node camera ros2 run buddybot_vision camera_node --ros-args -p width:="${CAMERA_WIDTH}" -p height:="${CAMERA_HEIGHT}" -p fps:="${CAMERA_FPS}" -p publish_rate:="${CAMERA_PUBLISH_RATE}" -p pixel_format:="${CAMERA_PIXEL_FORMAT}" -p buffer_size:="${CAMERA_BUFFER_SIZE}" -p discard_buffered_frames:="${CAMERA_DISCARD_BUFFERED_FRAMES}" -p opencv_threads:="${CAMERA_OPENCV_THREADS}"
  fi
  start_node detector ros2 run buddybot_vision detector_node --ros-args -p detection_interval:="${DETECT_INTERVAL}" -p confidence_threshold:="${DETECT_CONFIDENCE}" -p hog_confidence_threshold:="${DETECT_HOG_CONFIDENCE}" -p hog_resize_width:="${DETECT_HOG_RESIZE_WIDTH}" -p allow_hog_fallback:="${DETECT_ALLOW_HOG_FALLBACK_PARAM}" -p allow_cascade_fallback:="${DETECT_ALLOW_CASCADE_FALLBACK_PARAM}" -p publish_debug_image:="${DETECT_PUBLISH_DEBUG_IMAGE_PARAM}" -p opencv_threads:="${DETECT_OPENCV_THREADS}"
  start_node follow_controller ros2 run buddybot_vision follow_controller_node --ros-args -p image_width:="${CAMERA_WIDTH}" -p image_height:="${CAMERA_HEIGHT}" -p bbox_timeout_sec:="${FOLLOW_BBOX_TIMEOUT}" -p max_source_age_sec:="${FOLLOW_MAX_SOURCE_AGE}" -p height_gain:="${FOLLOW_HEIGHT_GAIN}" -p center_x_gain:="${FOLLOW_CENTER_GAIN}" -p target_height_ratio:="${FOLLOW_TARGET_HEIGHT}" -p max_linear_velocity:="${FOLLOW_MAX_LINEAR}" -p max_angular_velocity:="${FOLLOW_MAX_ANGULAR}" -p min_linear_velocity:="${FOLLOW_MIN_LINEAR}" -p deadzone_center:="${FOLLOW_CENTER_DEADZONE}" -p deadzone_height:="${FOLLOW_HEIGHT_DEADZONE}" -p command_rate_hz:="${FOLLOW_COMMAND_RATE}" -p linear_accel_limit:="${FOLLOW_LINEAR_ACCEL}" -p angular_accel_limit:="${FOLLOW_ANGULAR_ACCEL}" -p bbox_smoothing_alpha:="${FOLLOW_BBOX_SMOOTHING_ALPHA}" -p bbox_filter_reset_sec:="${FOLLOW_BBOX_FILTER_RESET_SEC}" -p allow_reverse:="${FOLLOW_ALLOW_REVERSE_PARAM}" -p visible_forward_velocity:="${FOLLOW_VISIBLE_FORWARD}" -p visible_forward_center_deadzone:="${FOLLOW_VISIBLE_FORWARD_CENTER_DEADZONE}" -p visible_forward_max_height_ratio:="${FOLLOW_VISIBLE_FORWARD_MAX_HEIGHT}" -p forward_yaw_trim:="${FOLLOW_FORWARD_YAW_TRIM}" -p forward_yaw_trim_center_deadzone:="${FOLLOW_FORWARD_YAW_TRIM_CENTER_DEADZONE}" -p near_turn_suppress_area_ratio:="${FOLLOW_NEAR_TURN_AREA}" -p near_turn_suppress_width_ratio:="${FOLLOW_NEAR_TURN_WIDTH}" -p close_stop_area_ratio:="${FOLLOW_CLOSE_STOP_AREA}" -p close_stop_width_ratio:="${FOLLOW_CLOSE_STOP_WIDTH}" -p close_stop_top_ratio:="${FOLLOW_CLOSE_STOP_TOP}" -p close_stop_min_height_ratio:="${FOLLOW_CLOSE_STOP_MIN_HEIGHT}" -p use_lidar_distance:="${FOLLOW_USE_LIDAR_DISTANCE_PARAM}" -p scan_forward_center_deg:="${BUDDYBOT_SCAN_FORWARD_CENTER_DEG:-180.0}" -p person_lidar_sector_deg:="${FOLLOW_LIDAR_SECTOR}" -p target_distance_m:="${FOLLOW_TARGET_DISTANCE}" -p distance_deadzone_m:="${FOLLOW_DISTANCE_DEADZONE}" -p min_follow_distance_m:="${FOLLOW_MIN_DISTANCE}" -p lidar_distance_gain:="${FOLLOW_LIDAR_GAIN}"
  ensure_lidar_stream "camera startup" || true
fi
start_node waypoint_manager ros2 run buddybot_nav waypoint_manager_node
start_node slam ros2 launch slam_toolbox online_async_launch.py
start_node panel ros2 run buddybot_panel panel_server

sleep 3
if [[ "$LIDAR_STREAM_CONFIRMED" -ne 1 ]] && ! scan_streaming 8 && ! scan_available; then
  echo "[mapping] warning: /scan is not being published yet"
  echo "[mapping] start your LiDAR driver first, then rerun this script"
  show_lidar_log_tail
fi

if ! is_truthy "$DISABLE_CAMERA" && ! camera_streaming 8; then
  echo "[mapping] warning: /camera/image_raw is not being published yet"
  echo "[mapping] check: tail -n 120 $LOG_DIR/camera.log"
fi

echo
echo "[mapping] mapping panel is running"
echo "[mapping] panel url: http://127.0.0.1:8090"
if [[ "$LIDAR_STARTED" -eq 1 ]]; then
  echo "[mapping] lidar driver: auto-started"
else
  echo "[mapping] lidar driver: not auto-started; /scan must already exist"
fi
echo "[mapping] logs: $LOG_DIR"
echo "[mapping] press Ctrl+C to stop everything"

while true; do
  sleep 2
done
