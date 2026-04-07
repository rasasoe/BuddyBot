#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK_SCRIPT="$ROOT_DIR/scripts/check_all_devices.sh"

run_section() {
  local title="$1"
  shift
  echo "===== $title ====="
  "$@" 2>&1 || true
  echo
}

first_camera_device() {
  if command -v v4l2-ctl >/dev/null 2>&1; then
    v4l2-ctl --list-devices 2>/dev/null | awk '
      /^[^\t].*\(/ {
        current_usb = ($0 ~ /usb/i)
        next
      }
      /^\t\/dev\/video[0-9]+$/ {
        if (current_usb) {
          gsub(/^\t/, "", $1)
          print $1
          exit
        }
      }
    '
  fi
}

echo "[diag] Pi5 full device + ROS stack diagnosis"
echo "[diag] repo root: $ROOT_DIR"
echo

run_section "lsusb" lsusb
run_section "/dev/serial/by-id" ls -l /dev/serial/by-id
run_section "v4l2 devices" v4l2-ctl --list-devices
run_section "arecord devices" arecord -l

CAMERA_DEVICE="$(first_camera_device || true)"
if [[ -n "${CAMERA_DEVICE:-}" ]]; then
  run_section "camera stream smoke test ($CAMERA_DEVICE)" \
    v4l2-ctl -d "$CAMERA_DEVICE" --stream-mmap=3 --stream-count=10
else
  echo "===== camera stream smoke test ====="
  echo "[diag] skipped: no /dev/video* device found"
  echo
fi

if [[ -f "$CHECK_SCRIPT" ]]; then
  run_section "check_all_devices" bash "$CHECK_SCRIPT"
else
  echo "===== check_all_devices ====="
  echo "[diag] skipped: $CHECK_SCRIPT not executable"
  echo
fi

echo "[diag] done"
