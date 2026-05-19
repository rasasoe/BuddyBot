#!/usr/bin/env python3
"""
Offline-first voice interface for BuddyBot.

This node can operate without BuddyBot AI:

- accepts recognized text on `/voice/text`
- optionally listens to a local microphone when SpeechRecognition is installed
- requires a wake phrase such as "buddybot" / "버디봇"
- executes local control commands directly through ROS topics
- publishes spoken/text responses on `/voice/response`

If `offline_mode` is disabled, it can still forward unmatched requests to the
BuddyBot AI server as a secondary path.
"""

from __future__ import annotations

import queue
import shutil
import subprocess
import threading
import time
from typing import List, Optional

import requests
import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Bool, String

try:
    import speech_recognition as sr
except ImportError:
    sr = None


class VoiceInterface(Node):
    def __init__(self):
        super().__init__("voice_interface")
        self.declare_parameter("offline_mode", True)
        self.declare_parameter("command_enabled", True)
        self.declare_parameter("enable_microphone", False)
        self.declare_parameter("allow_online_recognition", True)
        self.declare_parameter("recognition_backend", "google")
        self.declare_parameter("recognition_language", "ko-KR")
        self.declare_parameter("phrase_time_limit", 2.6)
        self.declare_parameter("wake_timeout_sec", 10.0)
        self.declare_parameter("pause_threshold", 0.45)
        self.declare_parameter("non_speaking_duration", 0.25)
        self.declare_parameter("dynamic_energy_threshold", False)
        self.declare_parameter("energy_threshold", 80.0)
        self.declare_parameter("max_energy_threshold", 220.0)
        self.declare_parameter("ambient_adjust_duration", 0.2)
        self.declare_parameter("manual_override_ignore_sec", 2.0)
        self.declare_parameter(
            "wake_words",
            ["버디봇", "버디봇아", "버디", "buddybot", "buddy"],
        )
        self.declare_parameter("manual_speed", 0.44)
        self.declare_parameter("strafe_speed", 0.30)
        self.declare_parameter("rotate_speed", 0.60)
        self.declare_parameter("enable_speaker_output", True)
        self.declare_parameter("speaker_backend", "auto")
        self.declare_parameter("speaker_voice_ko", "ko")
        self.declare_parameter("speaker_voice_en", "en-us")
        self.declare_parameter("speaker_rate_wpm", 180)
        self.declare_parameter("speak_command_responses", False)
        self.declare_parameter("buddybot_ai_url", "http://127.0.0.1:8000")

        self.offline_mode = bool(self.get_parameter("offline_mode").value)
        self.command_enabled = bool(self.get_parameter("command_enabled").value)
        self.server_assistant_enabled = not self.offline_mode
        self.enable_microphone = bool(self.get_parameter("enable_microphone").value)
        self.allow_online_recognition = bool(self.get_parameter("allow_online_recognition").value)
        self.recognition_backend = str(self.get_parameter("recognition_backend").value).strip().lower()
        self.recognition_language = str(self.get_parameter("recognition_language").value).strip()
        self.phrase_time_limit = float(self.get_parameter("phrase_time_limit").value)
        self.wake_timeout_sec = float(self.get_parameter("wake_timeout_sec").value)
        self.pause_threshold = float(self.get_parameter("pause_threshold").value)
        self.non_speaking_duration = float(self.get_parameter("non_speaking_duration").value)
        self.dynamic_energy_threshold = bool(self.get_parameter("dynamic_energy_threshold").value)
        self.energy_threshold = float(self.get_parameter("energy_threshold").value)
        self.max_energy_threshold = float(self.get_parameter("max_energy_threshold").value)
        self.ambient_adjust_duration = float(self.get_parameter("ambient_adjust_duration").value)
        self.manual_override_ignore_sec = float(self.get_parameter("manual_override_ignore_sec").value)
        self.wake_words = [
            item.strip().lower()
            for item in self.get_parameter("wake_words").value
            if str(item).strip()
        ]
        self.manual_speed = float(self.get_parameter("manual_speed").value)
        self.strafe_speed = float(self.get_parameter("strafe_speed").value)
        self.rotate_speed = float(self.get_parameter("rotate_speed").value)
        self.enable_speaker_output = bool(self.get_parameter("enable_speaker_output").value)
        self.speaker_backend = str(self.get_parameter("speaker_backend").value).strip().lower()
        self.speaker_voice_ko = str(self.get_parameter("speaker_voice_ko").value).strip() or "ko"
        self.speaker_voice_en = str(self.get_parameter("speaker_voice_en").value).strip() or "en-us"
        self.speaker_rate_wpm = int(self.get_parameter("speaker_rate_wpm").value)
        self.speak_command_responses = bool(self.get_parameter("speak_command_responses").value)
        self.buddybot_ai_url = str(self.get_parameter("buddybot_ai_url").value).rstrip("/")

        status_qos = QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        self.response_pub = self.create_publisher(String, "/voice/response", 10)
        self.command_pub = self.create_publisher(String, "/voice/command_status", status_qos)
        self.manual_pub = self.create_publisher(Twist, "/cmd_vel_manual", 10)
        self.follow_pub = self.create_publisher(Bool, "/follow/enabled", 10)
        self.nav_cancel_pub = self.create_publisher(String, "/nav/cancel", 10)
        self.waypoint_goal_pub = self.create_publisher(String, "/nav/waypoint_goal", 10)
        self.create_subscription(String, "/voice/text", self.text_callback, 10)
        self.create_subscription(Bool, "/voice/enabled", self.voice_enabled_callback, status_qos)
        self.create_subscription(Bool, "/voice/assistant_enabled", self.voice_assistant_callback, status_qos)
        self.create_subscription(String, "/voice/server_url", self.voice_server_url_callback, status_qos)
        self.create_subscription(String, "/voice/manual_override", self.manual_override_callback, 10)
        self.create_subscription(String, "/voice/response", self.voice_response_callback, 10)
        self.create_subscription(String, "/system/command_status", self.system_status_callback, 10)
        self.create_subscription(String, "/nav/navigation_status", self.navigation_status_callback, 10)
        self.manual_timer = self.create_timer(0.1, self.manual_publish_timer)

        self.follow_enabled = False
        self._manual_active = False
        self._manual_linear_x = 0.0
        self._manual_linear_y = 0.0
        self._manual_angular_z = 0.0
        self._last_wake_time = 0.0
        self._manual_override_until = 0.0
        self._system_status = "idle"
        self._navigation_status = "idle"

        self._recognizer = sr.Recognizer() if sr is not None else None
        if self._recognizer is not None:
            self._recognizer.energy_threshold = self.energy_threshold
            self._recognizer.pause_threshold = self.pause_threshold
            self._recognizer.non_speaking_duration = self.non_speaking_duration
            self._recognizer.dynamic_energy_threshold = self.dynamic_energy_threshold
        self._audio_thread: Optional[threading.Thread] = None
        self._audio_stop = threading.Event()
        self._speaker_thread: Optional[threading.Thread] = None
        self._speaker_queue: "queue.Queue[str]" = queue.Queue()
        self._speaker_backend_command = ""
        self._speaker_warned_missing_backend = False
        self._local_speech_allowlist = {"네.", "말씀하세요."}

        mode = "offline-local" if self.offline_mode else "ai-bridge"
        self.get_logger().info(f"Voice interface ready in {mode} mode")
        self.get_logger().info(f"Wake words: {', '.join(self.wake_words)}")
        self.get_logger().info(f"Command processing: {'enabled' if self.command_enabled else 'disabled'}")
        self.get_logger().info(f"Microphone listener: {'enabled' if self.enable_microphone else 'disabled'}")
        self.get_logger().info(
            f"Recognition: backend={self.recognition_backend}, language={self.recognition_language}, "
            f"online={'enabled' if self.allow_online_recognition else 'disabled'}, "
            f"phrase={self.phrase_time_limit}s, pause={self.pause_threshold}s, "
            f"energy={self.energy_threshold:.0f}, max_energy={self.max_energy_threshold:.0f}, "
            f"dynamic_energy={self.dynamic_energy_threshold}"
        )
        self.get_logger().info(f"Speaker output: {'enabled' if self.enable_speaker_output else 'disabled'}")
        self.get_logger().info(
            f"Local command speech: {'enabled' if self.speak_command_responses else 'wake-only'}"
        )

        if self.enable_microphone:
            self.start_microphone_listener()
        if self.enable_speaker_output:
            self.start_speaker_output()

    def text_callback(self, msg: String) -> None:
        user_text = msg.data.strip()
        if not user_text:
            return

        self.handle_text(user_text, source="topic")

    def voice_response_callback(self, msg: String) -> None:
        text = msg.data.strip()
        if not text:
            return
        if (
            not self.server_assistant_enabled
            and not self.speak_command_responses
            and text not in self._local_speech_allowlist
        ):
            return
        self.enqueue_speech(text)

    def voice_enabled_callback(self, msg: Bool) -> None:
        self.command_enabled = bool(msg.data)
        if not self.command_enabled:
            self._clear_manual_motion()
        state = "enabled" if self.command_enabled else "disabled"
        self._publish_status(f"voice_mode:{state}")
        self.get_logger().info(f"Voice command processing {state}")

    def voice_assistant_callback(self, msg: Bool) -> None:
        self.server_assistant_enabled = bool(msg.data)
        self.offline_mode = not self.server_assistant_enabled
        mode = "server-assistant" if self.server_assistant_enabled else "local-command"
        self._publish_status(f"voice_assistant:{mode}")
        self.get_logger().info(f"Voice assistant mode -> {mode}")

    def voice_server_url_callback(self, msg: String) -> None:
        server_url = msg.data.strip().rstrip("/")
        if not server_url:
            return
        self.buddybot_ai_url = server_url
        self._publish_status(f"voice_server_url:{server_url}")

    def manual_override_callback(self, msg: String) -> None:
        reason = msg.data.strip() or "manual"
        self._manual_override_until = time.time() + max(0.0, self.manual_override_ignore_sec)
        self._clear_manual_motion()
        self._publish_status(f"manual_override:{reason}")

    def system_status_callback(self, msg: String) -> None:
        self._system_status = msg.data

    def navigation_status_callback(self, msg: String) -> None:
        self._navigation_status = msg.data

    def manual_publish_timer(self) -> None:
        if not self._manual_active:
            return

        twist = Twist()
        twist.linear.x = self._manual_linear_x
        twist.linear.y = self._manual_linear_y
        twist.angular.z = self._manual_angular_z
        self.manual_pub.publish(twist)

    def handle_text(self, text: str, source: str = "unknown") -> None:
        cleaned = text.strip()
        if not cleaned:
            return

        if not self.command_enabled:
            self._publish_status(f"ignored:{source}:voice_disabled")
            return

        if source == "microphone" and time.time() < self._manual_override_until:
            self._publish_status(f"ignored:{source}:manual_override")
            return

        self._publish_status(f"heard:{source}:{cleaned}")
        answer = self._handle_offline_command(
            cleaned,
            allow_help=not self.server_assistant_enabled,
        )

        if not answer and self.server_assistant_enabled:
            answer = self._forward_to_ai(cleaned)

        if answer:
            self._publish_response(answer)
            self.get_logger().info(f"Voice handled ({source}): {cleaned} -> {answer}")

    def _handle_offline_command(self, message: str, *, allow_help: bool = True) -> str:
        text = self._normalize_text(message)
        if not text:
            return ""

        wake_triggered = False
        command_text = text
        for wake_word in self.wake_words:
            if text == wake_word:
                self._last_wake_time = time.time()
                return "네."
            if text.startswith(f"{wake_word} "):
                command_text = text[len(wake_word):].strip()
                wake_triggered = True
                break
            if text.startswith(wake_word) and len(text) > len(wake_word):
                command_text = text[len(wake_word):].strip()
                wake_triggered = True
                break

        now = time.time()
        if wake_triggered:
            self._last_wake_time = now
        elif now - self._last_wake_time > self.wake_timeout_sec:
            return ""

        if not command_text:
            return "말씀하세요."

        if any(keyword in command_text for keyword in ("stop", "halt", "brake", "정지", "멈춰", "스톱")):
            self._set_follow_enabled(False)
            self._clear_manual_motion()
            self._cancel_navigation()
            return "정지."

        if any(keyword in command_text for keyword in ("forward", "go ahead", "앞으로", "전진")):
            self._start_manual_motion(self.manual_speed, 0.0, 0.0)
            return "전진."

        if any(keyword in command_text for keyword in ("backward", "reverse", "back", "뒤로", "후진")):
            self._start_manual_motion(-self.manual_speed, 0.0, 0.0)
            return "후진."

        if any(keyword in command_text for keyword in ("strafe left", "slide left", "왼쪽 이동", "왼쪽으로")):
            self._start_manual_motion(0.0, self.strafe_speed, 0.0)
            return "왼쪽."

        if any(keyword in command_text for keyword in ("strafe right", "slide right", "오른쪽 이동", "오른쪽으로")):
            self._start_manual_motion(0.0, -self.strafe_speed, 0.0)
            return "오른쪽."

        if any(keyword in command_text for keyword in ("turn left", "rotate left", "좌회전", "왼쪽 회전")):
            self._start_manual_motion(0.0, 0.0, self.rotate_speed)
            return "좌회전."

        if any(keyword in command_text for keyword in ("turn right", "rotate right", "우회전", "오른쪽 회전")):
            self._start_manual_motion(0.0, 0.0, -self.rotate_speed)
            return "우회전."

        if any(keyword in command_text for keyword in ("follow stop", "unfollow", "추종 중지", "따라오지마", "추종 꺼")):
            self._set_follow_enabled(False)
            return "추종 중지."

        if any(keyword in command_text for keyword in ("follow", "track user", "따라와", "추종", "사용자 추종", "추종 시작", "추종 켜")):
            self._set_follow_enabled(True)
            return "추종 시작."

        if "kitchen" in command_text or "주방" in command_text or "부엌" in command_text:
            self._send_waypoint("kitchen")
            return "주방 이동."

        if "living room" in command_text or "거실" in command_text:
            self._send_waypoint("living_room_center")
            return "거실 이동."

        if "charge" in command_text or "충전" in command_text or "도킹" in command_text:
            self._send_waypoint("charging_station")
            return "충전 이동."

        if any(keyword in command_text for keyword in ("status", "state", "상태", "지금 상태")):
            return self._build_status_response()

        if not allow_help:
            return ""
        return "명령을 이해하지 못했습니다. 전진, 정지, 좌회전, 주방, 추종 시작처럼 말씀해 주세요."

    def _normalize_text(self, text: str) -> str:
        cleaned = text.lower().strip()
        for mark in (",", ".", "?", "!", ":", ";", "，", "。", "？", "！", "、", "~", "…"):
            cleaned = cleaned.replace(mark, " ")
        for prefix in ("hey ", "ok ", "okay ", "저기 ", "야 "):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        cleaned = " ".join(cleaned.split())
        return cleaned

    def _build_status_response(self) -> str:
        movement = "정지"
        if self._manual_active:
            movement = "수동 이동 중"
        if self.follow_enabled:
            movement = "추종 중"
        if self._navigation_status not in ("", "idle"):
            movement = f"내비게이션 {self._navigation_status}"
        return f"동작 {movement}. 상태 {self._system_status}."

    def _start_manual_motion(self, linear_x: float, linear_y: float, angular_z: float) -> None:
        self._set_follow_enabled(False)
        self._cancel_navigation()
        self._manual_active = True
        self._manual_linear_x = linear_x
        self._manual_linear_y = linear_y
        self._manual_angular_z = angular_z

    def _clear_manual_motion(self) -> None:
        self._manual_active = False
        self._manual_linear_x = 0.0
        self._manual_linear_y = 0.0
        self._manual_angular_z = 0.0
        self.manual_pub.publish(Twist())

    def _set_follow_enabled(self, enabled: bool) -> None:
        self.follow_enabled = enabled
        msg = Bool()
        msg.data = enabled
        self.follow_pub.publish(msg)
        if enabled:
            self._clear_manual_motion()
            self._cancel_navigation()

    def _cancel_navigation(self) -> None:
        msg = String()
        msg.data = "voice_cancel"
        self.nav_cancel_pub.publish(msg)

    def _send_waypoint(self, name: str) -> None:
        self._set_follow_enabled(False)
        self._clear_manual_motion()
        self._cancel_navigation()
        msg = String()
        msg.data = name
        self.waypoint_goal_pub.publish(msg)

    def _forward_to_ai(self, user_text: str) -> str:
        if self.offline_mode:
            return ""
        try:
            response = requests.post(
                f"{self.buddybot_ai_url}/chat",
                json={"message": user_text},
                timeout=15,
            )
            response.raise_for_status()
            answer = response.json().get("response", "").strip()
            return answer or "응답이 비어 있습니다."
        except requests.RequestException as exc:
            error_message = f"voice_bridge_error:{exc}"
            self._publish_status(error_message)
            self.get_logger().error(error_message)
            return "로컬 음성 명령만 사용할 수 있습니다."

    def start_microphone_listener(self) -> None:
        if sr is None:
            self.get_logger().warn("speech_recognition is not installed; microphone listener disabled")
            self._publish_status("microphone_unavailable:speech_recognition_missing")
            return

        if self._audio_thread is not None:
            return

        self._audio_thread = threading.Thread(target=self._microphone_loop, daemon=True)
        self._audio_thread.start()

    def _microphone_loop(self) -> None:
        recognizer = self._recognizer
        if recognizer is None or sr is None:
            return

        try:
            microphone = sr.Microphone()
        except Exception as exc:
            self.get_logger().error(f"Failed to open microphone: {exc}")
            self._publish_status(f"microphone_open_failed:{exc}")
            return

        try:
            with microphone as source:
                if self.ambient_adjust_duration > 0.0:
                    recognizer.adjust_for_ambient_noise(source, duration=self.ambient_adjust_duration)
                if not self.dynamic_energy_threshold:
                    min_energy = max(1.0, self.energy_threshold)
                    max_energy = self.max_energy_threshold if self.max_energy_threshold > 0.0 else min_energy
                    recognizer.energy_threshold = min(max(recognizer.energy_threshold, min_energy), max_energy)
                self._publish_status(f"microphone_ready:energy={recognizer.energy_threshold:.0f}")
                while not self._audio_stop.is_set():
                    try:
                        audio = recognizer.listen(
                            source,
                            timeout=1.0,
                            phrase_time_limit=self.phrase_time_limit,
                        )
                    except sr.WaitTimeoutError:
                        continue
                    except Exception as exc:
                        self._publish_status(f"microphone_listen_failed:{exc}")
                        self.get_logger().error(f"Microphone listen failed: {exc}")
                        break

                    transcript = self._recognize_audio(recognizer, audio)
                    if transcript:
                        self.handle_text(transcript, source="microphone")
        except Exception as exc:
            self._publish_status(f"microphone_loop_failed:{exc}")
            self.get_logger().error(f"Microphone loop failed: {exc}")

    def _recognize_audio(self, recognizer, audio) -> str:
        backend = self.recognition_backend

        if backend in ("google", "auto") and self.allow_online_recognition:
            if shutil.which("flac") is None:
                self._publish_status("google_recognition_missing_flac")
                self.get_logger().warn("Google recognition needs the flac command line tool; install it with: sudo apt install -y flac")
                if backend == "google":
                    return ""
            else:
                try:
                    transcript = recognizer.recognize_google(audio, language=self.recognition_language).strip()
                    if transcript:
                        self._publish_status(f"recognized:google:{transcript}")
                    return transcript
                except Exception as exc:
                    self._publish_status(f"google_recognition_failed:{exc}")
                    self.get_logger().warn(f"Google recognition failed: {exc}")
                    if backend == "google":
                        return ""

        if backend in ("sphinx", "auto"):
            try:
                transcript = recognizer.recognize_sphinx(audio).strip()
                if transcript:
                    self._publish_status(f"recognized:sphinx:{transcript}")
                return transcript
            except Exception as exc:
                self._publish_status(f"sphinx_failed:{exc}")
                self.get_logger().warn(f"Sphinx recognition failed: {exc}")

        self._publish_status(f"recognition_backend_unavailable:{backend}")
        return ""

    def _publish_response(self, text: str) -> None:
        msg = String()
        msg.data = text
        self.response_pub.publish(msg)
        self._publish_status("response_published")

    def start_speaker_output(self) -> None:
        if self._speaker_thread is not None:
            return

        backend = self._detect_speaker_backend()
        if not backend:
            self.enable_speaker_output = False
            if not self._speaker_warned_missing_backend:
                self._speaker_warned_missing_backend = True
                self.get_logger().warn("No local TTS backend found; USB speaker output disabled")
                self._publish_status("speaker_backend_missing")
            return

        self._speaker_backend_command = backend
        self._speaker_thread = threading.Thread(target=self._speaker_loop, daemon=True)
        self._speaker_thread.start()
        self.get_logger().info(f"Speaker output ready via {backend}")
        self._publish_status(f"speaker_ready:{backend}")

    def _detect_speaker_backend(self) -> str:
        if self.speaker_backend and self.speaker_backend != "auto":
            return self.speaker_backend if shutil.which(self.speaker_backend) else ""
        for candidate in ("espeak-ng", "espeak", "spd-say"):
            if shutil.which(candidate):
                return candidate
        return ""

    def enqueue_speech(self, text: str) -> None:
        if not self.enable_speaker_output:
            return
        cleaned = text.strip()
        if not cleaned:
            return
        while self._speaker_queue.qsize() > 2:
            try:
                self._speaker_queue.get_nowait()
            except queue.Empty:
                break
        self._speaker_queue.put(cleaned)

    def _speaker_loop(self) -> None:
        while not self._audio_stop.is_set():
            try:
                text = self._speaker_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if not text:
                continue
            try:
                self._speak_text(text)
            except Exception as exc:
                self.get_logger().warn(f"Speaker playback failed: {exc}")
                self._publish_status(f"speaker_failed:{exc}")

    def _speak_text(self, text: str) -> None:
        backend = self._speaker_backend_command
        if not backend:
            return

        if backend == "spd-say":
            completed = subprocess.run(
                [backend, text],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if completed.returncode != 0:
                stderr = (completed.stderr or completed.stdout or "").strip()
                raise RuntimeError(stderr or f"{backend} exited with {completed.returncode}")
            return

        voice = self.speaker_voice_ko if any("\uac00" <= ch <= "\ud7a3" for ch in text) else self.speaker_voice_en
        command = [backend, "-s", str(self.speaker_rate_wpm)]
        if voice:
            command.extend(["-v", voice])
        command.append(text)

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if completed.returncode != 0 and voice:
            command = [backend, "-s", str(self.speaker_rate_wpm), text]
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        if completed.returncode != 0:
            stderr = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(stderr or f"{backend} exited with {completed.returncode}")

    def _publish_status(self, text: str) -> None:
        msg = String()
        msg.data = text
        self.command_pub.publish(msg)

    def destroy_node(self):
        self._audio_stop.set()
        if self._speaker_thread is not None:
            self._speaker_queue.put("")
        self._clear_manual_motion()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = VoiceInterface()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
