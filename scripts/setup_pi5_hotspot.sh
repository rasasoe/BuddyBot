#!/usr/bin/env bash
set -euo pipefail

SSID="${1:-BuddyBot-Local}"
PASSWORD="${2:-BuddyBot1234!}"
CONNECTION_NAME="${3:-buddybot-hotspot}"
ADDRESS="${4:-192.168.50.1/24}"

echo "[hotspot] configuring Pi5 hotspot with NetworkManager"
echo "[hotspot] ssid: $SSID"
echo "[hotspot] connection name: $CONNECTION_NAME"
echo "[hotspot] address: $ADDRESS"

if ! command -v nmcli >/dev/null 2>&1; then
  echo "[hotspot] error: nmcli not found"
  echo "[hotspot] install NetworkManager first"
  exit 1
fi

if [[ ${#PASSWORD} -lt 8 ]]; then
  echo "[hotspot] error: password must be at least 8 characters"
  exit 1
fi

sudo nmcli connection delete "$CONNECTION_NAME" >/dev/null 2>&1 || true

sudo nmcli connection add \
  type wifi \
  ifname wlan0 \
  con-name "$CONNECTION_NAME" \
  autoconnect yes \
  ssid "$SSID"

sudo nmcli connection modify "$CONNECTION_NAME" \
  802-11-wireless.mode ap \
  802-11-wireless.band bg \
  ipv4.method shared \
  ipv4.addresses "$ADDRESS" \
  ipv6.method ignore \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.psk "$PASSWORD"

echo
echo "[hotspot] configured successfully"
echo "[hotspot] start with:"
echo "  bash scripts/start_pi5_hotspot.sh \"$CONNECTION_NAME\""
echo "[hotspot] phone connection:"
echo "  SSID: $SSID"
echo "  Password: $PASSWORD"
echo "[hotspot] panel url after connect:"
echo "  http://192.168.50.1:8090"
