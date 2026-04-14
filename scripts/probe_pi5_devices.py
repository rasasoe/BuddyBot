#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import os
import subprocess
import time
import urllib.error
import urllib.request

os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

try:
    import cv2
except Exception:
    cv2 = None

try:
    import serial
except Exception:
    serial = None

try:
    from serial.tools import list_ports
except Exception:
    list_ports = None


def _port_label(port: str) -> str:
    resolved = os.path.realpath(port)
    parts = [
        os.path.basename(resolved).lower(),
        os.path.basename(port).lower(),
        port.lower(),
        resolved.lower(),
        _usb_metadata_label(port),
    ]
    return " ".join(part for part in parts if part)


def _usb_metadata_label(port: str) -> str:
    if list_ports is None:
        return ""
    resolved = os.path.realpath(port)
    try:
        for info in list_ports.comports():
            info_device = getattr(info, "device", "") or ""
            if not info_device:
                continue
            if resolved not in {os.path.realpath(info_device), info_device} and port != info_device:
                continue
            parts = [
                str(getattr(info, "description", "") or ""),
                str(getattr(info, "manufacturer", "") or ""),
                str(getattr(info, "product", "") or ""),
                str(getattr(info, "interface", "") or ""),
                str(getattr(info, "serial_number", "") or ""),
            ]
            vid = getattr(info, "vid", None)
            pid = getattr(info, "pid", None)
            if vid is not None and pid is not None:
                parts.append(f"{vid:04x}:{pid:04x}")
            return " ".join(part.lower() for part in parts if part)
    except Exception:
        return ""
    return ""


def _port_priority(port: str) -> tuple[int, str]:
    label = _port_label(port)
    resolved = os.path.realpath(port)
    if "/dev/serial/by-id/" in port:
        return (0, port)
    if "/dev/serial/by-path/" in port:
        return (1, port)
    if any(token in label for token in ("raspberry pi pico", "micropython", "2e8a:0005", "2e8a:000a", "pico")):
        return (2, port)
    if resolved.startswith("/dev/ttyACM"):
        return (3, port)
    if resolved.startswith("/dev/ttyUSB"):
        return (4, port)
    return (5, port)


def serial_candidates() -> list[str]:
    candidates: list[str] = []
    candidates.extend(sorted(glob.glob("/dev/serial/by-id/*")))
    candidates.extend(sorted(glob.glob("/dev/serial/by-path/*")))
    candidates.extend(sorted(glob.glob("/dev/ttyACM*")))
    candidates.extend(sorted(glob.glob("/dev/ttyUSB*")))
    if list_ports is not None:
        try:
            for info in list_ports.comports():
                if getattr(info, "device", ""):
                    candidates.append(str(info.device))
        except Exception:
            pass

    unique: list[str] = []
    seen: set[str] = set()
    for port in sorted(candidates, key=_port_priority):
        if not port or port in seen:
            continue
        unique.append(port)
        seen.add(port)
    return unique


def pico_probe_candidates(candidates: list[str]) -> list[str]:
    preferred: list[str] = []
    fallback: list[str] = []
    for port in candidates:
        label = _port_label(port)
        if any(token in label for token in ("cp210", "silicon_labs", "lidar", "rplidar", "sllidar")):
            continue
        if any(token in label for token in ("raspberry pi pico", "micropython", "pico", "ttyacm", "2e8a:0005", "2e8a:000a")):
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
    candidates.extend(_v4l_camera_devices())
    candidates.extend(sorted(glob.glob("/dev/v4l/by-id/*")))
    candidates.extend(sorted(glob.glob("/dev/v4l/by-path/*usb*")))
    candidates.extend(_direct_video_candidates())

    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        unique.append(candidate)
        seen.add(candidate)
    return unique


def _run_text_command(command: list[str]) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return (result.stdout or "").strip()
    except Exception:
        return ""


def _v4l2_groups() -> list[dict[str, list[str] | str]]:
    output = _run_text_command(["v4l2-ctl", "--list-devices"])
    if not output:
        return []

    groups: list[dict[str, list[str] | str]] = []
    current: dict[str, list[str] | str] | None = None
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if not raw_line.startswith((" ", "\t")):
            if current is not None:
                groups.append(current)
            current = {"label": line.rstrip(":"), "devices": []}
            continue
        if current is None:
            continue
        device = line.strip()
        if device.startswith("/dev/video"):
            current["devices"].append(device)

    if current is not None:
        groups.append(current)
    return groups


def _camera_group_priority(label: str) -> tuple[int, str]:
    lowered = label.lower()
    if any(token in lowered for token in ("pispbe", "rpivid", "bcm2835", "codec", "loopback")):
        return (9, lowered)
    if any(token in lowered for token in ("logitech", "webcam", "c920", "usb", "uvc", "camera")):
        return (0, lowered)
    return (4, lowered)


def _video_index(path: str) -> int:
    try:
        return int(os.path.basename(path).removeprefix("video"))
    except ValueError:
        return 999


def _v4l_camera_devices() -> list[str]:
    devices: list[str] = []
    for group in sorted(_v4l2_groups(), key=lambda item: _camera_group_priority(str(item.get("label", "")))):
        for device in sorted(group.get("devices", []), key=_video_index):
            if _video_index(device) > 9:
                continue
            devices.append(device)
    return devices


def _direct_video_candidates() -> list[str]:
    candidates: list[str] = []
    for candidate in sorted(glob.glob("/dev/video*"), key=_video_index):
        if _video_index(candidate) > 9:
            continue
        candidates.append(candidate)
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
    serial_by_path = sorted(glob.glob("/dev/serial/by-path/*"))
    all_serial_candidates = serial_candidates()
    pico_port = probe_pico_port(pico_probe_candidates(all_serial_candidates))
    lidar_port = detect_lidar_port(all_serial_candidates, pico_port)

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
        "SERIAL_CANDIDATES": " ".join(all_serial_candidates),
        "SERIAL_BY_ID": " ".join(serial_by_id),
        "SERIAL_BY_PATH": " ".join(serial_by_path),
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
