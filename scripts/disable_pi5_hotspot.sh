#!/usr/bin/env bash
set -euo pipefail

CONNECTION_NAME="${1:-buddybot-hotspot}"

if ! command -v nmcli >/dev/null 2>&1; then
  echo "[hotspot] error: nmcli not found"
  exit 1
fi

echo "[hotspot] disabling autoconnect for: $CONNECTION_NAME"
sudo nmcli connection modify "$CONNECTION_NAME" connection.autoconnect no >/dev/null 2>&1 || true

echo "[hotspot] deleting hotspot connection if present: $CONNECTION_NAME"
sudo nmcli connection delete "$CONNECTION_NAME" >/dev/null 2>&1 || true

echo "[hotspot] done"
echo "[hotspot] reboot will no longer fall back to this hotspot profile"
