#!/usr/bin/env bash
set -euo pipefail

CONNECTION_NAME="${1:-buddybot-hotspot}"
ALLOW_HOTSPOT="${BUDDYBOT_ALLOW_HOTSPOT:-0}"

if [[ "$ALLOW_HOTSPOT" != "1" ]]; then
  echo "[hotspot] disabled by default"
  echo "[hotspot] this script will not enable AP mode unless you explicitly allow it"
  echo "[hotspot] to force-enable once:"
  echo "  BUDDYBOT_ALLOW_HOTSPOT=1 bash scripts/start_pi5_hotspot.sh \"$CONNECTION_NAME\""
  exit 1
fi

if ! command -v nmcli >/dev/null 2>&1; then
  echo "[hotspot] error: nmcli not found"
  exit 1
fi

echo "[hotspot] bringing up connection: $CONNECTION_NAME"
sudo nmcli connection up "$CONNECTION_NAME"

echo
echo "[hotspot] hotspot is active"
echo "[hotspot] connect your phone to the Pi5 Wi-Fi and open:"
echo "  http://192.168.50.1:8090"
echo
nmcli -f NAME,DEVICE,TYPE,STATE connection show --active
