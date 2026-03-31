#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="$ROOT_DIR/software/pi5/ros2_ws/src"
FIX_MODE="${1:-}"

echo "[doctor] workspace: $SRC_DIR"

check_marker() {
  local pkg_dir="$1"
  local pkg_name
  pkg_name="$(basename "$pkg_dir")"
  local marker="$pkg_dir/resource/$pkg_name"

  if [[ -f "$pkg_dir/setup.py" ]]; then
    if [[ ! -f "$marker" ]]; then
      echo "[doctor] missing resource marker: $marker"
      if [[ "$FIX_MODE" == "--fix" ]]; then
        mkdir -p "$pkg_dir/resource"
        : > "$marker"
        echo "[doctor] created resource marker: $marker"
      fi
    fi

    if [[ ! -f "$pkg_dir/$pkg_name/__init__.py" ]]; then
      echo "[doctor] missing python package init: $pkg_dir/$pkg_name/__init__.py"
      if [[ "$FIX_MODE" == "--fix" ]]; then
        mkdir -p "$pkg_dir/$pkg_name"
        printf '"""%s package."""\n' "$pkg_name" > "$pkg_dir/$pkg_name/__init__.py"
        echo "[doctor] created __init__.py for $pkg_name"
      fi
    fi
  fi
}

for pkg_dir in "$SRC_DIR"/buddybot_*; do
  [[ -d "$pkg_dir" ]] || continue
  check_marker "$pkg_dir"
done

if grep -q '</package>.*</package>' "$SRC_DIR/buddybot_nav/package.xml" 2>/dev/null; then
  echo "[doctor] buddybot_nav/package.xml looks malformed"
  exit 1
fi

echo "[doctor] complete"
