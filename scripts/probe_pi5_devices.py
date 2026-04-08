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


def _port_label(port: str) -> str:
    return os.path.basename(os.path.realpath(port)).lower() + " " + os.path.basename(port).lower() + " " + port.lower()


def pico_probe_candidates(candidates: list[str]) -> list[str]:
    preferred: list[str] = []
    fallback: list[str] = []
    for port in candidates:
        label = _port_label(port)
        if any(token in label for token in ("cp210", "silicon_labs", "lidar", "rplidar", "sllidar")):
            continue
        if any(token in label for token in ("micropython", "pico", "ttyacm")):
            preferred.append(port)
        else:
            fallback.append(port)
    return preferred + fallback


def detect_lidar_port(candidates: list[str], pico_port: str) -> str:
    preferred: list[str] = []
    fallback: list[str] = []
    for port in candidates:
        if port == pico_port:
            continue
        label = _port_label(port)
        resolved = os.path.realpath(port)
        if any(token in label for token in ("micropython", "pico")):
            continue
        if any(token in label for token in ("cp210", "silicon_labs", "lidar", "rplidar", "sllidar", "ttyusb")):
            preferred.append(port)
        elif resolved.startswith("/dev/ttyUSB"):
            fallback.append(port)
    ordered = preferred + fallback
    return ordered[0] if ordered else ""


def camera_candidates(preferred: str = "") -> list[str]:
    candidates: list[str] = []
    if preferred:
        candidates.append(preferred)
    candidates.extend(sorted(glob.glob("/dev/v4l/by-id/*")))
    candidates.extend(sorted(glob.glob("/dev/v4l/by-path/*usb*")))
    candidates.extend(sorted(glob.glob("/dev/video*")))
    return candidates


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


def detect_camera_device(preferred: str = "") -> str:
    if cv2 is None:
        return ""
    candidates = camera_candidates(preferred)

    tried: set[str] = set()
    for candidate in candidates:
        resolved = os.path.realpath(candidate)
        if resolved.startswith("/dev/video") and not os.access(resolved, os.R_OK | os.W_OK):
            continue
        probe_order = [candidate]
        if resolved != candidate:
            probe_order.append(resolved)

        for probe in probe_order:
            if probe in tried:
                continue
            tried.add(probe)

            cap = None
            try:
                if hasattr(cv2, "CAP_V4L2"):
                    cap = cv2.VideoCapture(probe, cv2.CAP_V4L2)
                else:
                    cap = cv2.VideoCapture(probe)
                if not cap.isOpened() and resolved.startswith("/dev/video") and hasattr(cv2, "CAP_V4L2"):
                    cap.release()
                    cap = cv2.VideoCapture(int(resolved.removeprefix("/dev/video")), cv2.CAP_V4L2)
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
    pico_port = probe_pico_port(pico_probe_candidates(serial_candidates))
    lidar_port = detect_lidar_port(serial_candidates, pico_port)

    v4l_by_id = sorted(glob.glob("/dev/v4l/by-id/*"))
    camera_device = ""
    for candidate in v4l_by_id:
        if "video-index0" in candidate:
            camera_device = detect_camera_device(candidate)
            if camera_device:
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
