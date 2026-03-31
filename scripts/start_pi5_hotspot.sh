#!/usr/bin/env bash
set -euo pipefail

CONNECTION_NAME="${1:-buddybot-hotspot}"

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
