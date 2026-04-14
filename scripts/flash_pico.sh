#!/usr/bin/env bash
# flash_pico.sh - upload BuddyBot firmware files to Pico via mpremote
#
# Usage:
#   bash scripts/flash_pico.sh               # auto-detect port
#   bash scripts/flash_pico.sh /dev/ttyACM0  # specify port
#
# Requires: mpremote  (pip3 install mpremote)
# If not installed this script will install it automatically.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIRMWARE_DIR="$ROOT_DIR/firmware/pico_motor_controller"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
info()  { echo -e "${GREEN}[pico]${NC} $*"; }
warn()  { echo -e "${YELLOW}[pico]${NC} $*"; }
error() { echo -e "${RED}[pico]${NC} $*" >&2; }

PICO_FILES=(
    config.py
    encoder.py
    kinematics.py
    main.py
    motor_driver.py
    pid.py
    pins.py
    safety.py
    state.py
    uart_protocol.py
    watchdog.py
)

if ! command -v mpremote &>/dev/null; then
    warn "mpremote not found, installing via pip3..."
    pip3 install --quiet mpremote
fi

detect_pico_port() {
    local detected=""

    if [[ -f "$ROOT_DIR/scripts/probe_pi5_devices.py" ]]; then
        detected="$(python3 "$ROOT_DIR/scripts/probe_pi5_devices.py" 2>/dev/null | awk -F= '/^PICO_PORT=/{print $2; exit}' || true)"
        if [[ -n "$detected" ]]; then
            echo "$detected"
            return 0
        fi
    fi

    detected="$(ls /dev/serial/by-id/usb-MicroPython_Board* 2>/dev/null | head -1 || true)"
    if [[ -n "$detected" ]]; then
        echo "$detected"
        return 0
    fi

    for port in /dev/ttyACM0 /dev/ttyACM1 /dev/ttyACM2; do
        if [[ -e "$port" ]]; then
            echo "$port"
            return 0
        fi
    done

    return 1
}

PICO_PORT="${1:-}"

if [[ -z "$PICO_PORT" ]]; then
    PICO_PORT="$(detect_pico_port || true)"
fi

if [[ -z "$PICO_PORT" ]]; then
    error "Pico not found. Connect Pico and retry, or pass port as argument:"
    error "  bash scripts/flash_pico.sh /dev/ttyACM0"
    error "  If Pico is not showing as MicroPython yet, replug it or enter BOOTSEL first."
    exit 1
fi

info "Pico port: $PICO_PORT"
info "Firmware : $FIRMWARE_DIR"

info "Stopping running firmware (soft reset)..."
mpremote connect "$PICO_PORT" exec "import machine; machine.reset()" 2>/dev/null || true
sleep 1.5

UPLOADED=0
FAILED=0

for fname in "${PICO_FILES[@]}"; do
    src="$FIRMWARE_DIR/$fname"
    if [[ ! -f "$src" ]]; then
        warn "  skip  $fname (not found)"
        continue
    fi
    echo -n "  upload $fname ... "
    if mpremote connect "$PICO_PORT" cp "$src" ":$fname" 2>/dev/null; then
        echo -e "${GREEN}OK${NC}"
        ((UPLOADED++)) || true
    else
        echo -e "${RED}FAIL${NC}"
        ((FAILED++)) || true
    fi
done

info "Rebooting Pico..."
mpremote connect "$PICO_PORT" exec "import machine; machine.reset()" 2>/dev/null || true

echo ""
if [[ "$FAILED" -eq 0 ]]; then
    info "Done - $UPLOADED files uploaded, Pico rebooting."
else
    error "Done - $UPLOADED uploaded, $FAILED failed. Check output above."
    exit 1
fi
