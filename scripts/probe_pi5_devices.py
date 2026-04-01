#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import time
import urllib.error
import urllib.request

try:
    import cv2
except Exception:
    cv2 = None

try:
    import serial
except Exception:
    serial = None


def probe_pico_port(candidates: list[str], baudrate: int = 115200) -> str:
    if serial is None:
        return ""
    for port in candidates:
        try:
            with serial.Serial(port=port, baudrate=baudrate, timeout=0.25, write_timeout=0.5) as ser:
                time.sleep(0.15)
                ser.reset_input_buffer()
                ser.write(b"HB\n")
                ser.flush()
                deadline = time.time() + 0.8
                while time.time() < deadline:
                    raw = ser.readline()
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="ignore").strip()
                    if line.startswith(("FEEDBACK:", "ACK", "STAT", "RPM")):
                        return port
        except Exception:
            continue
    return ""


def detect_camera_device() -> str:
    if cv2 is None:
        return ""
    for candidate in sorted(glob.glob("/dev/video*")):
        cap = None
        try:
            if hasattr(cv2, "CAP_V4L2"):
                cap = cv2.VideoCapture(candidate, cv2.CAP_V4L2)
            else:
                cap = cv2.VideoCapture(candidate)
            if not cap.isOpened():
                continue
            ok, _ = cap.read()
            if ok:
                return candidate
        except Exception:
            continue
        finally:
            if cap is not None:
                cap.release()
    return ""


def detect_microphone() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["arecord", "-l"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        text = (result.stdout or "") + (result.stderr or "")
        return ("card " in text.lower(), text.strip())
    except Exception as exc:
        return (False, str(exc))


def detect_ai_server(url: str) -> str:
    if not url:
        return "unknown"
    health_url = url.rstrip("/") + "/health"
    try:
        with urllib.request.urlopen(health_url, timeout=1.0) as response:
            return "online" if 200 <= response.status < 300 else "offline"
    except urllib.error.URLError:
        return "offline"
    except Exception:
        return "offline"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shell", action="store_true")
    parser.add_argument("--server-url", default=os.getenv("BUDDYBOT_AI_URL", ""))
    args = parser.parse_args()

    serial_by_id = sorted(glob.glob("/dev/serial/by-id/*"))
    serial_candidates = serial_by_id + sorted(glob.glob("/dev/ttyACM*")) + sorted(glob.glob("/dev/ttyUSB*"))
    pico_port = probe_pico_port(serial_candidates)

    lidar_port = ""
    for candidate in serial_candidates:
        if candidate != pico_port:
            lidar_port = candidate
            break

    v4l_by_id = sorted(glob.glob("/dev/v4l/by-id/*"))
    camera_device = ""
    for candidate in v4l_by_id:
        if "video-index0" in candidate:
            camera_device = candidate
            break
    if not camera_device:
        camera_device = detect_camera_device()
    mic_ok, mic_info = detect_microphone()
    server_state = detect_ai_server(args.server_url)

    data = {
        "PICO_PORT": pico_port,
        "LIDAR_PORT": lidar_port,
        "CAMERA_DEVICE": camera_device,
        "MIC_AVAILABLE": "1" if mic_ok else "0",
        "AI_SERVER_STATE": server_state,
        "SERIAL_CANDIDATES": " ".join(serial_candidates),
        "SERIAL_BY_ID": " ".join(serial_by_id),
        "V4L_BY_ID": " ".join(v4l_by_id),
        "MIC_INFO": mic_info.replace("\n", " | "),
    }

    if args.shell:
        for key, value in data.items():
            escaped = value.replace("'", "'\"'\"'")
            print(f"{key}='{escaped}'")
    else:
        for key, value in data.items():
            print(f"{key}={value}")


if __name__ == "__main__":
    main()
