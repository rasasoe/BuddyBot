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

import os
import queue
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None


class VoiceInterface(Node):
    WAKE_ALIAS_REPLACEMENTS = (
        ("버디 봇아", "버디봇아"),
        ("바디봇아", "버디봇아"),
        ("바디 봇아", "버디봇아"),
        ("버디보트", "버디봇"),
        ("버디 보트", "버디봇"),
        ("버디 봇", "버디봇"),
        ("바디봇", "버디봇"),
        ("바디 봇", "버디봇"),
        ("버디보", "버디봇"),
        ("버디 보", "버디봇"),
        ("buddy bot", "buddybot"),
    )

    def __init__(self):
        super().__init__("voice_interface")
        self.declare_parameter("offline_mode", True)
        self.declare_parameter("command_enabled", False)
        self.declare_parameter("enable_microphone", False)
        self.declare_parameter("allow_online_recognition", True)
        self.declare_parameter("recognition_backend", "hybrid")
        self.declare_parameter("recognition_language", "ko-KR")
        self.declare_parameter("server_stt_enabled", True)
        self.declare_parameter("server_stt_timeout_sec", 4.0)
        self.declare_parameter("server_stt_cooldown_sec", 10.0)
        self.declare_parameter("local_whisper_enabled", True)
        self.declare_parameter("local_whisper_model_size", "tiny")
        self.declare_parameter("local_whisper_device", "cpu")
        self.declare_parameter("local_whisper_compute_type", "int8")
        self.declare_parameter("local_whisper_language", "ko")
        self.declare_parameter("google_fallback_enabled", True)
        self.declare_parameter("phrase_time_limit", 2.6)
        self.declare_parameter("moving_phrase_time_limit", 1.2)
        self.declare_parameter("wake_timeout_sec", 10.0)
        self.declare_parameter("pause_threshold", 0.45)
        self.declare_parameter("non_speaking_duration", 0.25)
        self.declare_parameter("dynamic_energy_threshold", True)
        self.declare_parameter("ambient_adjust_duration", 1.0)
        self.declare_parameter("google_timeout_sec", 1.8)
        self.declare_parameter("manual_override_ignore_sec", 2.0)
        self.declare_parameter("manual_command_timeout_sec", 2.0)
        self.declare_parameter("nudge_duration_sec", 2.5)
        self.declare_parameter("continuous_command_max_sec", 0.0)
        self.declare_parameter("zero_burst_count", 4)
        self.declare_parameter(
            "wake_words",
            [
                "버디봇아",
                "버디봇",
                "버디 봇아",
                "버디 봇",
                "바디봇",
                "바디 봇",
                "버디보",
                "버디 보",
                "버디보트",
                "buddybot",
                "buddy bot",
                "버디",
                "buddy",
            ],
        )
        self.declare_parameter("manual_speed", 0.46)
        self.declare_parameter("strafe_speed", 0.30)
        self.declare_parameter("rotate_speed", 0.60)
        self.declare_parameter("forward_yaw_trim", -0.003)
        self.declare_parameter("backward_yaw_trim", -0.003)
        self.declare_parameter("strafe_left_yaw_trim", 0.0)
        self.declare_parameter("strafe_right_yaw_trim", 0.0)
        self.declare_parameter("enable_speaker_output", True)
        self.declare_parameter("speaker_backend", "auto")
        self.declare_parameter("speaker_voice_ko", "ko")
        self.declare_parameter("speaker_voice_en", "en-us")
        self.declare_parameter("speaker_rate_wpm", 180)
        self.declare_parameter("speak_command_responses", False)
        self.declare_parameter("server_tts_enabled", True)
        self.declare_parameter("server_tts_timeout_sec", 12.0)
        self.declare_parameter("system_sound_dir", "")
        self.declare_parameter("piper_model_path", "")
        self.declare_parameter("audio_player", "auto")
        self.declare_parameter("buddybot_ai_url", "http://127.0.0.1:8000")

        self.offline_mode = bool(self.get_parameter("offline_mode").value)
        self.command_enabled = bool(self.get_parameter("command_enabled").value)
        self.server_assistant_enabled = not self.offline_mode
        self.enable_microphone = bool(self.get_parameter("enable_microphone").value)
        self.allow_online_recognition = bool(self.get_parameter("allow_online_recognition").value)
        self.recognition_backend = str(self.get_parameter("recognition_backend").value).strip().lower()
        self.recognition_language = str(self.get_parameter("recognition_language").value).strip()
        self.server_stt_enabled = bool(self.get_parameter("server_stt_enabled").value)
        self.server_stt_timeout_sec = max(0.5, float(self.get_parameter("server_stt_timeout_sec").value))
        self.server_stt_cooldown_sec = max(0.0, float(self.get_parameter("server_stt_cooldown_sec").value))
        self.local_whisper_enabled = bool(self.get_parameter("local_whisper_enabled").value)
        self.local_whisper_model_size = str(self.get_parameter("local_whisper_model_size").value).strip() or "tiny"
        self.local_whisper_device = str(self.get_parameter("local_whisper_device").value).strip() or "cpu"
        self.local_whisper_compute_type = str(self.get_parameter("local_whisper_compute_type").value).strip() or "int8"
        self.local_whisper_language = str(self.get_parameter("local_whisper_language").value).strip() or "ko"
        self.google_fallback_enabled = bool(self.get_parameter("google_fallback_enabled").value)
        self.phrase_time_limit = float(self.get_parameter("phrase_time_limit").value)
        self.moving_phrase_time_limit = float(self.get_parameter("moving_phrase_time_limit").value)
        self.wake_timeout_sec = float(self.get_parameter("wake_timeout_sec").value)
        self.pause_threshold = float(self.get_parameter("pause_threshold").value)
        self.non_speaking_duration = float(self.get_parameter("non_speaking_duration").value)
        self.dynamic_energy_threshold = bool(self.get_parameter("dynamic_energy_threshold").value)
        self.ambient_adjust_duration = float(self.get_parameter("ambient_adjust_duration").value)
        self.google_timeout_sec = float(self.get_parameter("google_timeout_sec").value)
        self.manual_override_ignore_sec = float(self.get_parameter("manual_override_ignore_sec").value)
        self.manual_command_timeout_sec = float(self.get_parameter("manual_command_timeout_sec").value)
        self.nudge_duration_sec = float(self.get_parameter("nudge_duration_sec").value)
        self.continuous_command_max_sec = float(self.get_parameter("continuous_command_max_sec").value)
        self.zero_burst_count = max(1, int(self.get_parameter("zero_burst_count").value))
        normalized_wake_words = [
            self._normalize_text(str(item))
            for item in self.get_parameter("wake_words").value
            if str(item).strip()
        ]
        self.wake_words = list(dict.fromkeys(sorted(normalized_wake_words, key=len, reverse=True)))
        self.manual_speed = float(self.get_parameter("manual_speed").value)
        self.strafe_speed = float(self.get_parameter("strafe_speed").value)
        self.rotate_speed = float(self.get_parameter("rotate_speed").value)
        self.forward_yaw_trim = float(self.get_parameter("forward_yaw_trim").value)
        self.backward_yaw_trim = float(self.get_parameter("backward_yaw_trim").value)
        self.strafe_left_yaw_trim = float(self.get_parameter("strafe_left_yaw_trim").value)
        self.strafe_right_yaw_trim = float(self.get_parameter("strafe_right_yaw_trim").value)
        self.enable_speaker_output = bool(self.get_parameter("enable_speaker_output").value)
        self.speaker_backend = str(self.get_parameter("speaker_backend").value).strip().lower()
        self.speaker_voice_ko = str(self.get_parameter("speaker_voice_ko").value).strip() or "ko"
        self.speaker_voice_en = str(self.get_parameter("speaker_voice_en").value).strip() or "en-us"
        self.speaker_rate_wpm = int(self.get_parameter("speaker_rate_wpm").value)
        self.speak_command_responses = bool(self.get_parameter("speak_command_responses").value)
        self.server_tts_enabled = bool(self.get_parameter("server_tts_enabled").value)
        self.server_tts_timeout_sec = max(1.0, float(self.get_parameter("server_tts_timeout_sec").value))
        system_sound_dir = str(self.get_parameter("system_sound_dir").value).strip()
        self.system_sound_dir: Optional[Path] = Path(system_sound_dir).expanduser() if system_sound_dir else None
        self.piper_model_path = str(self.get_parameter("piper_model_path").value).strip()
        self.audio_player = str(self.get_parameter("audio_player").value).strip().lower() or "auto"
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
        self.manual_timer = self.create_timer(0.05, self.manual_publish_timer)

        self.follow_enabled = False
        self._manual_active = False
        self._manual_linear_x = 0.0
        self._manual_linear_y = 0.0
        self._manual_angular_z = 0.0
        self._manual_until = 0.0
        self._manual_command_mode = "idle"
        self._manual_intent = "idle"
        self._last_wake_time = 0.0
        self._manual_override_until = 0.0
        self._system_status = "idle"
        self._navigation_status = "idle"

        self._recognizer = sr.Recognizer() if sr is not None else None
        if self._recognizer is not None:
            self._recognizer.pause_threshold = self.pause_threshold
            self._recognizer.non_speaking_duration = self.non_speaking_duration
            self._recognizer.dynamic_energy_threshold = self.dynamic_energy_threshold
            self._recognizer.operation_timeout = max(0.5, self.google_timeout_sec)
        self._audio_thread: Optional[threading.Thread] = None
        self._audio_stop = threading.Event()
        self._speaker_thread: Optional[threading.Thread] = None
        self._speaker_queue: "queue.Queue[Tuple[str, str]]" = queue.Queue()
        self._speaker_backend_command = ""
        self._audio_player_command = ""
        self._speaker_warned_missing_backend = False
        self._local_whisper_model = None
        self._local_whisper_lock = threading.Lock()
        self._local_whisper_warned_missing = False
        self._local_whisper_retry_after = 0.0
        self._server_stt_retry_after = 0.0
        self._speech_category_lock = threading.Lock()
        self._speech_category_overrides: Dict[str, List[str]] = {}
        self._local_speech_allowlist = {
            "네.",
            "말씀하세요.",
            "전진.",
            "지속 전진.",
            "후진.",
            "왼쪽.",
            "오른쪽.",
            "좌회전.",
            "우회전.",
            "정지.",
            "추종 시작.",
            "추종 중지.",
            "로컬 음성 명령만 사용할 수 있습니다.",
        }

        mode = "offline-local" if self.offline_mode else "ai-bridge"
        self.get_logger().info(f"Voice interface ready in {mode} mode")
        self.get_logger().info(f"Wake words: {', '.join(self.wake_words)}")
        self.get_logger().info(f"Command processing: {'enabled' if self.command_enabled else 'disabled'}")
        self.get_logger().info(f"Microphone listener: {'enabled' if self.enable_microphone else 'disabled'}")
        self.get_logger().info(
            f"Recognition: backend={self.recognition_backend}, language={self.recognition_language}, "
            f"online={'enabled' if self.allow_online_recognition else 'disabled'}, "
            f"phrase={self.phrase_time_limit}s, pause={self.pause_threshold}s, "
            f"dynamic_energy={self.dynamic_energy_threshold}, ambient={self.ambient_adjust_duration}s, "
            f"google_timeout={self.google_timeout_sec}s"
        )
        self.get_logger().info(
            f"Hybrid STT: server={'enabled' if self.server_stt_enabled else 'disabled'} "
            f"timeout={self.server_stt_timeout_sec:.1f}s cooldown={self.server_stt_cooldown_sec:.1f}s, "
            f"local_whisper={'enabled' if self.local_whisper_enabled else 'disabled'} "
            f"model={self.local_whisper_model_size}/{self.local_whisper_device}/{self.local_whisper_compute_type}, "
            f"google_fallback={'enabled' if self.google_fallback_enabled else 'disabled'}"
        )
        self.get_logger().info(
            f"Motion voice: manual_speed={self.manual_speed}, "
            f"yaw_trim f/b/sl/sr={self.forward_yaw_trim}/{self.backward_yaw_trim}/"
            f"{self.strafe_left_yaw_trim}/{self.strafe_right_yaw_trim}, "
            f"continuous_max={self.continuous_command_max_sec}s"
        )
        self.get_logger().info(f"Speaker output: {'enabled' if self.enable_speaker_output else 'disabled'}")
        self.get_logger().info(
            f"Local command speech: {'enabled' if self.speak_command_responses else 'wake-only'}"
        )
        self.get_logger().info(
            f"Hybrid TTS: server={'enabled' if self.server_tts_enabled else 'disabled'}, "
            f"system_sound_dir={self.system_sound_dir or '-'}, "
            f"piper_model={'configured' if self.piper_model_path else 'unset'}"
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
        category = self._take_speech_category(text)
        if category is None:
            category = "ai" if self.server_assistant_enabled else "system"
        if (
            category == "system"
            and not self.server_assistant_enabled
            and not self.speak_command_responses
            and text not in self._local_speech_allowlist
        ):
            return
        self.enqueue_speech(text, category=category)

    def voice_enabled_callback(self, msg: Bool) -> None:
        self.command_enabled = bool(msg.data)
        if not self.command_enabled:
            self._last_wake_time = 0.0
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
        if self._manual_active:
            self._clear_manual_motion()
        else:
            self._reset_manual_motion_state()
        self._publish_status(f"manual_override:{reason}")

    def system_status_callback(self, msg: String) -> None:
        self._system_status = msg.data

    def navigation_status_callback(self, msg: String) -> None:
        self._navigation_status = msg.data

    def manual_publish_timer(self) -> None:
        if not self._manual_active:
            return

        if self._manual_until > 0.0 and time.time() >= self._manual_until:
            command_mode = self._manual_command_mode
            self._clear_manual_motion()
            if command_mode == "continuous":
                self._publish_status("voice_manual:continuous_safety_stop")
            else:
                self._publish_status("voice_manual:nudge_auto_stop")
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

        if self._is_stop_command(cleaned):
            self._publish_status(f"heard:{source}:{cleaned}")
            self._log_voice_classification(
                raw_text=cleaned,
                normalized_text=self._normalize_text(cleaned),
                matched_intent="stop",
                matched_keywords=self._matched_keywords(self._strip_wake_prefix(cleaned), self.STOP_WORDS),
                command_mode="stop",
                stop_priority_applied=True,
            )
            answer = self._stop_robot()
            self._publish_response(answer, category="emergency")
            self.get_logger().info(f"Voice safety stop ({source}): {cleaned} -> {answer}")
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

        category = "system"
        if not answer and self.server_assistant_enabled:
            answer = self._forward_to_ai(cleaned)
            category = "ai"

        if answer:
            self._publish_response(answer, category=category)
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

        if self._is_stop_command(command_text):
            self._log_voice_classification(
                raw_text=message,
                normalized_text=text,
                matched_intent="stop",
                matched_keywords=self._matched_keywords(command_text, self.STOP_WORDS),
                command_mode="stop",
                stop_priority_applied=True,
            )
            return self._stop_robot()

        if self._is_motion_negation(command_text):
            self._publish_status("voice_manual:blocked_negative")
            self._log_voice_classification(
                raw_text=message,
                normalized_text=text,
                matched_intent="blocked_negative",
                matched_keywords=self._matched_keywords(command_text, self.MOTION_WORDS),
                command_mode="ignored",
                stop_priority_applied=False,
            )
            return "이동하지 않겠습니다."

        if self._is_explanation_request(command_text) and self._has_motion_word(command_text):
            self._publish_status("voice_manual:blocked_ambiguous")
            self._log_voice_classification(
                raw_text=message,
                normalized_text=text,
                matched_intent="blocked_explanation",
                matched_keywords=self._matched_keywords(command_text, self.MOTION_WORDS),
                command_mode="ignored",
                stop_priority_applied=False,
            )
            return "" if not allow_help else "설명 요청으로 판단해서 이동하지 않았습니다."

        if self._matches_any(command_text, self.CONTINUOUS_FORWARD_WORDS) or self._is_continuous_forward(command_text):
            self._log_voice_classification(
                raw_text=message,
                normalized_text=text,
                matched_intent="forward",
                matched_keywords=self._matched_keywords(command_text, self.CONTINUOUS_FORWARD_WORDS),
                command_mode="continuous",
                stop_priority_applied=False,
            )
            self._start_manual_motion(
                self.manual_speed,
                0.0,
                self.forward_yaw_trim,
                self.continuous_command_max_sec,
                mode="continuous",
                intent="forward",
            )
            return "지속 전진."

        if self._matches_any(command_text, self.FORWARD_WORDS):
            self._log_voice_classification(
                raw_text=message,
                normalized_text=text,
                matched_intent="forward",
                matched_keywords=self._matched_keywords(command_text, self.FORWARD_WORDS),
                command_mode="continuous",
                stop_priority_applied=False,
            )
            self._start_manual_motion(
                self.manual_speed,
                0.0,
                self.forward_yaw_trim,
                self.continuous_command_max_sec,
                mode="continuous",
                intent="forward",
            )
            return "전진."

        if any(keyword in command_text for keyword in ("backward", "reverse", "back", "뒤로", "후진")):
            self._start_manual_motion(-self.manual_speed, 0.0, self.backward_yaw_trim, self.nudge_duration_sec, mode="nudge", intent="backward")
            return "후진."

        if any(keyword in command_text for keyword in ("strafe left", "slide left", "왼쪽 이동", "왼쪽으로", "좌측 이동", "좌측으로")):
            self._start_manual_motion(0.0, self.strafe_speed, self.strafe_left_yaw_trim, self.nudge_duration_sec, mode="nudge", intent="strafe_left")
            return "왼쪽."

        if any(keyword in command_text for keyword in ("strafe right", "slide right", "오른쪽 이동", "오른쪽으로", "우측 이동", "우측으로")):
            self._start_manual_motion(0.0, -self.strafe_speed, self.strafe_right_yaw_trim, self.nudge_duration_sec, mode="nudge", intent="strafe_right")
            return "오른쪽."

        if any(keyword in command_text for keyword in ("turn left", "rotate left", "좌회전", "왼쪽 회전")):
            self._start_manual_motion(0.0, 0.0, self.rotate_speed, self.nudge_duration_sec, mode="nudge", intent="rotate_left")
            return "좌회전."

        if any(keyword in command_text for keyword in ("turn right", "rotate right", "우회전", "오른쪽 회전")):
            self._start_manual_motion(0.0, 0.0, -self.rotate_speed, self.nudge_duration_sec, mode="nudge", intent="rotate_right")
            return "우회전."

        if any(keyword in command_text for keyword in ("follow stop", "unfollow", "추종 정지", "추종 중지", "따라오지 마", "따라오지마", "그만 따라와", "추종 꺼")):
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

    def _normalize_basic_text(self, text: str) -> str:
        cleaned = text.lower().strip()
        for mark in (",", ".", "?", "!", ":", ";", "，", "。", "？", "！", "、", "~", "…"):
            cleaned = cleaned.replace(mark, " ")
        for prefix in ("hey ", "ok ", "okay ", "저기 ", "야 "):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        cleaned = " ".join(cleaned.split())
        return cleaned

    def _normalize_text(self, text: str) -> str:
        cleaned = self._normalize_basic_text(text)
        for alias, canonical in self.WAKE_ALIAS_REPLACEMENTS:
            cleaned = cleaned.replace(alias, canonical)
        return " ".join(cleaned.split())

    FORWARD_WORDS = (
        "forward",
        "go ahead",
        "전진",
        "앞으로",
        "앞으로 가",
        "가자",
        "직진",
    )
    CONTINUOUS_FORWARD_WORDS = (
        "continue forward",
        "keep going",
        "계속 전진",
        "계속 앞으로",
        "앞으로 계속",
        "앞으로 계속 가",
        "주행 시작",
        "계속 가",
        "쭉 가",
        "쭉 전진",
        "계속 직진",
    )
    STOP_WORDS = (
        "stop",
        "halt",
        "brake",
        "cancel",
        "멈춰줘",
        "멈춰 줘",
        "멈추세요",
        "멈춰주세요",
        "그만해",
        "세워줘",
        "정지",
        "정지해",
        "멈춰",
        "멈추어",
        "멈춰라",
        "멈춤",
        "멈추",
        "스톱",
        "스탑",
        "중지",
        "취소",
        "그만",
        "세워",
    )
    NEGATION_WORDS = (
        "하지 마",
        "하지마",
        "가지 마",
        "가지마",
        "움직이지 마",
        "움직이지마",
        "이동하지 마",
        "이동하지마",
        "하지 말",
        "가지 말",
        "움직이지 말",
        "이동하지 말",
        "don't",
        "do not",
    )
    EXPLANATION_WORDS = (
        "방법",
        "설명",
        "알려",
        "알려줘",
        "뭐야",
        "무엇",
        "뜻",
        "코드",
        "어떻게",
        "how",
        "what",
        "explain",
    )
    MOTION_WORDS = FORWARD_WORDS + CONTINUOUS_FORWARD_WORDS + STOP_WORDS + (
        "후진",
        "뒤로",
        "좌회전",
        "우회전",
        "왼쪽",
        "오른쪽",
        "이동",
        "움직",
    )

    def _strip_wake_prefix(self, text: str) -> str:
        normalized = self._normalize_text(text)
        for wake_word in self.wake_words:
            if normalized == wake_word:
                return ""
            if normalized.startswith(f"{wake_word} "):
                return normalized[len(wake_word):].strip()
            if normalized.startswith(wake_word) and len(normalized) > len(wake_word):
                return normalized[len(wake_word):].strip()
        return normalized

    @staticmethod
    def _matches_any(text: str, words) -> bool:
        return any(word in text for word in words)

    def _matched_keywords(self, text: str, words) -> List[str]:
        normalized = self._normalize_text(text)
        return [word for word in words if word in normalized]

    def _has_motion_word(self, text: str) -> bool:
        return self._matches_any(text, self.MOTION_WORDS)

    def _is_motion_negation(self, text: str) -> bool:
        return self._has_motion_word(text) and self._matches_any(text, self.NEGATION_WORDS)

    def _is_explanation_request(self, text: str) -> bool:
        return self._matches_any(text, self.EXPLANATION_WORDS)

    def _is_continuous_forward(self, text: str) -> bool:
        has_forward = self._matches_any(text, ("forward", "전진", "앞으로", "직진", "가자"))
        has_continue = self._matches_any(text, ("continue", "keep", "계속", "쭉", "주행 시작"))
        return has_forward and has_continue

    def _is_stop_command(self, text: str) -> bool:
        normalized = self._strip_wake_prefix(text)
        if not self._matches_any(normalized, self.STOP_WORDS):
            return False
        if self._is_motion_negation(normalized):
            return False
        if self._is_explanation_request(normalized):
            return False
        return True

    def _preview_local_intent(self, text: str) -> str:
        command_text = self._strip_wake_prefix(text)
        if self._is_stop_command(command_text):
            return "stop"
        if self._is_motion_negation(command_text):
            return "blocked_negative"
        if self._is_explanation_request(command_text) and self._has_motion_word(command_text):
            return "blocked_explanation"
        if self._matches_any(command_text, self.CONTINUOUS_FORWARD_WORDS) or self._is_continuous_forward(command_text):
            return "forward"
        if self._matches_any(command_text, self.FORWARD_WORDS):
            return "forward"
        if any(keyword in command_text for keyword in ("backward", "reverse", "back", "뒤로", "후진")):
            return "backward"
        if any(keyword in command_text for keyword in ("strafe left", "slide left", "왼쪽 이동", "왼쪽으로", "좌측 이동", "좌측으로")):
            return "strafe_left"
        if any(keyword in command_text for keyword in ("strafe right", "slide right", "오른쪽 이동", "오른쪽으로", "우측 이동", "우측으로")):
            return "strafe_right"
        if any(keyword in command_text for keyword in ("turn left", "rotate left", "좌회전", "왼쪽 회전")):
            return "rotate_left"
        if any(keyword in command_text for keyword in ("turn right", "rotate right", "우회전", "오른쪽 회전")):
            return "rotate_right"
        if any(keyword in command_text for keyword in ("follow stop", "unfollow", "추종 정지", "추종 중지", "따라오지 마", "따라오지마", "그만 따라와", "추종 꺼")):
            return "follow_stop"
        if any(keyword in command_text for keyword in ("follow", "track user", "따라와", "추종", "사용자 추종", "추종 시작", "추종 켜")):
            return "follow_start"
        if "kitchen" in command_text or "주방" in command_text or "부엌" in command_text:
            return "waypoint_kitchen"
        if "living room" in command_text or "거실" in command_text:
            return "waypoint_living_room"
        if "charge" in command_text or "충전" in command_text or "도킹" in command_text:
            return "waypoint_charging"
        if any(keyword in command_text for keyword in ("status", "state", "상태", "지금 상태")):
            return "status"
        if not command_text and self._contains_wake_word(text):
            return "wake"
        return "unknown"

    def _is_local_robot_command(self, text: str) -> bool:
        return self._preview_local_intent(text) not in {"", "unknown", "wake"}

    def _matched_wake_alias(self, text: str) -> str:
        basic = self._normalize_basic_text(text)
        aliases = [alias for alias, _ in self.WAKE_ALIAS_REPLACEMENTS]
        aliases.extend(self.wake_words)
        for alias in sorted(set(aliases), key=len, reverse=True):
            if alias in basic:
                return alias
        normalized = self._normalize_text(text)
        for wake_word in self.wake_words:
            if wake_word in normalized:
                return wake_word
        return ""

    @staticmethod
    def _audio_duration_sec(audio) -> float:
        frame_data = getattr(audio, "frame_data", b"")
        sample_rate = max(1, int(getattr(audio, "sample_rate", 1)))
        sample_width = max(1, int(getattr(audio, "sample_width", 1)))
        return len(frame_data) / float(sample_rate * sample_width)

    def _log_stt_observation(self, *, backend: str, phase: str, audio, transcript: str) -> None:
        normalized = self._normalize_text(transcript)
        wake_alias = self._matched_wake_alias(transcript)
        wake_detected = bool(wake_alias)
        command_text = self._strip_wake_prefix(transcript) if wake_detected else normalized
        local_intent = self._preview_local_intent(transcript)
        self.get_logger().info(
            "stt_observation "
            f"backend={backend} phase={phase} raw_audio_duration={self._audio_duration_sec(audio):.2f}s "
            f"raw_stt_text={transcript!r} normalized_text={normalized!r} "
            f"wake_detected={str(wake_detected).lower()} wake_matched_alias={wake_alias or '-'} "
            f"command_text={command_text!r} local_intent={local_intent}"
        )

    def _recognize_local_observed(self, audio, *, phase: str) -> str:
        transcript = self._recognize_with_local_whisper(audio)
        self._log_stt_observation(
            backend="local_whisper",
            phase=phase,
            audio=audio,
            transcript=transcript,
        )
        return transcript

    def _log_voice_classification(
        self,
        *,
        raw_text: str,
        normalized_text: str,
        matched_intent: str,
        matched_keywords: List[str],
        command_mode: str,
        stop_priority_applied: bool,
    ) -> None:
        keyword_text = ",".join(matched_keywords) if matched_keywords else "-"
        self.get_logger().info(
            "voice_classification "
            f"raw_stt_text={raw_text!r} normalized_text={normalized_text!r} "
            f"matched_intent={matched_intent} matched_keywords={keyword_text} "
            f"command_mode={command_mode} stop_priority_applied={stop_priority_applied}"
        )

    def _stop_robot(self) -> str:
        self._set_follow_enabled(False)
        self._clear_manual_motion()
        self._cancel_navigation()
        self._publish_status("voice_manual:stop")
        return "정지."

    def _build_status_response(self) -> str:
        movement = "정지"
        if self._manual_active:
            movement = "수동 이동 중"
        if self.follow_enabled:
            movement = "추종 중"
        if self._navigation_status not in ("", "idle"):
            movement = f"내비게이션 {self._navigation_status}"
        return f"동작 {movement}. 상태 {self._system_status}."

    def _start_manual_motion(
        self,
        linear_x: float,
        linear_y: float,
        angular_z: float,
        duration_sec: float = 0.0,
        *,
        mode: str = "nudge",
        intent: str = "manual",
    ) -> None:
        self._set_follow_enabled(False)
        self._cancel_navigation()
        self._manual_active = True
        self._manual_linear_x = linear_x
        self._manual_linear_y = linear_y
        self._manual_angular_z = angular_z
        self._manual_until = time.time() + duration_sec if duration_sec > 0.0 else 0.0
        self._manual_command_mode = mode
        self._manual_intent = intent
        self._publish_status(f"voice_manual:{mode}_{intent}")

    def _clear_manual_motion(self) -> None:
        self._reset_manual_motion_state()
        for _ in range(self.zero_burst_count):
            self.manual_pub.publish(Twist())

    def _reset_manual_motion_state(self) -> None:
        self._manual_active = False
        self._manual_linear_x = 0.0
        self._manual_linear_y = 0.0
        self._manual_angular_z = 0.0
        self._manual_until = 0.0
        self._manual_command_mode = "idle"
        self._manual_intent = "idle"

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
                self._publish_status(f"microphone_ready:energy={recognizer.energy_threshold:.0f}")
                while not self._audio_stop.is_set():
                    try:
                        phrase_limit = self.phrase_time_limit
                        if self._manual_active or self.follow_enabled:
                            phrase_limit = min(self.phrase_time_limit, self.moving_phrase_time_limit)
                        audio = recognizer.listen(
                            source,
                            timeout=1.0,
                            phrase_time_limit=phrase_limit,
                        )
                    except sr.WaitTimeoutError:
                        continue
                    except Exception as exc:
                        self._publish_status(f"microphone_listen_failed:{exc}")
                        self.get_logger().error(f"Microphone listen failed: {exc}")
                        break

                    recognition_phase = self._recognition_phase()
                    transcript = self._recognize_audio(recognizer, audio, phase=recognition_phase)
                    if transcript:
                        self.handle_text(transcript, source="microphone")
        except Exception as exc:
            self._publish_status(f"microphone_loop_failed:{exc}")
            self.get_logger().error(f"Microphone loop failed: {exc}")

    def _recognition_phase(self) -> str:
        if not self.command_enabled:
            return "disabled"
        if self._manual_active or self.follow_enabled:
            return "safety"
        if time.time() - self._last_wake_time <= self.wake_timeout_sec:
            return "command"
        return "wake"

    def _recognize_audio(self, recognizer, audio, *, phase: str = "command") -> str:
        backend = self.recognition_backend

        if backend in ("hybrid", "auto"):
            return self._recognize_hybrid_audio(recognizer, audio, phase=phase)
        if backend == "server_whisper":
            return self._recognize_with_server_whisper(audio)
        if backend == "local_whisper":
            return self._recognize_with_local_whisper(audio)
        if backend == "google":
            return self._recognize_with_google(recognizer, audio)
        if backend == "sphinx":
            return self._recognize_with_sphinx(recognizer, audio)

        self._publish_status(f"recognition_backend_unavailable:{backend}")
        return ""

    def _recognize_hybrid_audio(self, recognizer, audio, *, phase: str) -> str:
        if phase == "disabled":
            local_transcript = self._recognize_local_observed(audio, phase=phase)
            if local_transcript and self._is_stop_command(local_transcript):
                self._publish_status(f"recognized:local_whisper_disabled_safety:{local_transcript}")
                return local_transcript
            return ""

        if phase == "wake":
            local_transcript = self._recognize_local_observed(audio, phase=phase)
            if local_transcript:
                if self._is_stop_command(local_transcript):
                    return local_transcript
                if self._contains_wake_word(local_transcript) and self._strip_wake_prefix(local_transcript):
                    if self._is_local_robot_command(local_transcript):
                        return local_transcript
                    server_transcript = self._recognize_with_server_whisper(audio)
                    return self._merge_confirmed_wake_transcript(local_transcript, server_transcript)
                if self._contains_wake_word(local_transcript):
                    return local_transcript

            server_transcript = self._recognize_with_server_whisper(audio)
            if server_transcript and (
                self._is_stop_command(server_transcript)
                or self._contains_wake_word(server_transcript)
            ):
                return server_transcript

            google_transcript = self._recognize_with_google_fallback(recognizer, audio)
            if google_transcript and (
                self._is_stop_command(google_transcript)
                or self._contains_wake_word(google_transcript)
            ):
                return google_transcript
            return ""

        if phase == "safety":
            local_transcript = self._recognize_local_observed(audio, phase=phase)
            if local_transcript and self._is_stop_command(local_transcript):
                self._publish_status(f"recognized:local_whisper_safety:{local_transcript}")
                return local_transcript
            if local_transcript and self._is_local_robot_command(local_transcript):
                return local_transcript
            return (
                self._recognize_with_server_whisper(audio)
                or local_transcript
                or self._recognize_with_google_fallback(recognizer, audio)
            )

        local_transcript = self._recognize_local_observed(audio, phase=phase)
        if local_transcript and self._is_local_robot_command(local_transcript):
            return local_transcript
        return (
            self._recognize_with_server_whisper(audio)
            or local_transcript
            or self._recognize_with_google_fallback(recognizer, audio)
        )

    def _recognize_with_server_whisper(self, audio) -> str:
        if not self.server_stt_enabled or time.monotonic() < self._server_stt_retry_after:
            return ""
        started_at = time.monotonic()
        try:
            response = requests.post(
                f"{self.buddybot_ai_url}/stt",
                data=self._audio_wav_bytes(audio),
                headers={"Content-Type": "audio/wav"},
                timeout=(1.0, self.server_stt_timeout_sec),
            )
            response.raise_for_status()
            transcript = str(response.json().get("text", "")).strip()
            if transcript:
                self._publish_status(f"recognized:server_whisper:{transcript}")
            return transcript
        except Exception as exc:
            elapsed = time.monotonic() - started_at
            self._server_stt_retry_after = time.monotonic() + self.server_stt_cooldown_sec
            self._publish_status(f"server_stt_failed:{elapsed:.2f}s:{exc}")
            self.get_logger().warn(
                f"Server Whisper STT failed after {elapsed:.2f}s; "
                f"using local fallback for {self.server_stt_cooldown_sec:.1f}s: {exc}"
            )
            return ""

    def _recognize_with_local_whisper(self, audio) -> str:
        if not self.local_whisper_enabled or time.monotonic() < self._local_whisper_retry_after:
            return ""
        if WhisperModel is None:
            if not self._local_whisper_warned_missing:
                self._local_whisper_warned_missing = True
                self._publish_status("local_whisper_missing")
                self.get_logger().warn(
                    "Local faster-whisper is not installed; run: "
                    "pip3 install --break-system-packages faster-whisper"
                )
            return ""

        temp_path = self._write_temp_audio(self._audio_wav_bytes(audio), suffix=".wav")
        try:
            model = self._get_local_whisper_model()
            segments, _ = model.transcribe(
                str(temp_path),
                language=self.local_whisper_language,
                beam_size=1,
                vad_filter=True,
            )
            transcript = "".join(segment.text for segment in segments).strip()
            if transcript:
                self._publish_status(f"recognized:local_whisper:{transcript}")
            return transcript
        except Exception as exc:
            self._local_whisper_retry_after = time.monotonic() + self.server_stt_cooldown_sec
            self._publish_status(f"local_whisper_failed:{exc}")
            self.get_logger().warn(f"Local faster-whisper failed: {exc}")
            return ""
        finally:
            temp_path.unlink(missing_ok=True)

    def _get_local_whisper_model(self):
        with self._local_whisper_lock:
            if self._local_whisper_model is None:
                self.get_logger().info(
                    f"Loading local faster-whisper model {self.local_whisper_model_size} "
                    f"on {self.local_whisper_device}/{self.local_whisper_compute_type}"
                )
                self._publish_status(f"local_whisper_loading:{self.local_whisper_model_size}")
                self._local_whisper_model = WhisperModel(
                    self.local_whisper_model_size,
                    device=self.local_whisper_device,
                    compute_type=self.local_whisper_compute_type,
                )
                self._publish_status(f"local_whisper_ready:{self.local_whisper_model_size}")
            return self._local_whisper_model

    def _recognize_with_google_fallback(self, recognizer, audio) -> str:
        if not self.google_fallback_enabled:
            return ""
        return self._recognize_with_google(recognizer, audio)

    def _recognize_with_google(self, recognizer, audio) -> str:
        if not self.allow_online_recognition:
            return ""
        if shutil.which("flac") is None:
            self._publish_status("google_recognition_missing_flac")
            self.get_logger().warn("Google recognition needs the flac command line tool; install it with: sudo apt install -y flac")
            return ""

        started_at = time.monotonic()
        previous_socket_timeout = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(max(0.5, self.google_timeout_sec))
            transcript = recognizer.recognize_google(audio, language=self.recognition_language).strip()
            if transcript:
                self._publish_status(f"recognized:google:{transcript}")
            return transcript
        except Exception as exc:
            elapsed = time.monotonic() - started_at
            if elapsed >= max(0.5, self.google_timeout_sec) * 0.9:
                self._publish_status(f"google_recognition_timeout:{elapsed:.2f}s")
                self.get_logger().warn(f"Google recognition timed out after {elapsed:.2f}s: {exc}")
            else:
                self._publish_status(f"google_recognition_failed:{exc}")
                self.get_logger().warn(f"Google recognition failed: {exc}")
            return ""
        finally:
            socket.setdefaulttimeout(previous_socket_timeout)

    def _recognize_with_sphinx(self, recognizer, audio) -> str:
        try:
            transcript = recognizer.recognize_sphinx(audio).strip()
            if transcript:
                self._publish_status(f"recognized:sphinx:{transcript}")
            return transcript
        except Exception as exc:
            self._publish_status(f"sphinx_failed:{exc}")
            self.get_logger().warn(f"Sphinx recognition failed: {exc}")
            return ""

    @staticmethod
    def _audio_wav_bytes(audio) -> bytes:
        return audio.get_wav_data(convert_rate=16000, convert_width=2)

    def _contains_wake_word(self, text: str) -> bool:
        normalized = self._normalize_text(text)
        return any(wake_word in normalized for wake_word in self.wake_words)

    def _merge_confirmed_wake_transcript(self, local_transcript: str, server_transcript: str) -> str:
        if not server_transcript:
            return local_transcript
        if self._contains_wake_word(server_transcript):
            return server_transcript

        normalized_local = self._normalize_text(local_transcript)
        for wake_word in self.wake_words:
            if wake_word in normalized_local:
                return f"{wake_word} {server_transcript}".strip()
        return local_transcript

    def _publish_response(self, text: str, *, category: str = "system") -> None:
        self._remember_speech_category(text, category)
        msg = String()
        msg.data = text
        self.response_pub.publish(msg)

    def _remember_speech_category(self, text: str, category: str) -> None:
        with self._speech_category_lock:
            categories = self._speech_category_overrides.setdefault(text, [])
            categories.append(category)

    def _take_speech_category(self, text: str) -> Optional[str]:
        with self._speech_category_lock:
            categories = self._speech_category_overrides.get(text)
            if not categories:
                return None
            category = categories.pop(0)
            if not categories:
                self._speech_category_overrides.pop(text, None)
            return category

    def start_speaker_output(self) -> None:
        if self._speaker_thread is not None:
            return

        backend = self._detect_speaker_backend()
        audio_player = self._detect_audio_player()
        if not backend and not audio_player:
            self.enable_speaker_output = False
            if not self._speaker_warned_missing_backend:
                self._speaker_warned_missing_backend = True
                self.get_logger().warn("No local TTS or audio playback backend found; USB speaker output disabled")
                self._publish_status("speaker_backend_missing")
            return

        self._speaker_backend_command = backend
        self._audio_player_command = audio_player
        self._speaker_thread = threading.Thread(target=self._speaker_loop, daemon=True)
        self._speaker_thread.start()
        self.get_logger().info(f"Speaker output ready via local={backend or '-'}, player={audio_player or '-'}")
        self._publish_status(f"speaker_ready:local={backend or '-'}:player={audio_player or '-'}")

    def _detect_speaker_backend(self) -> str:
        if self.speaker_backend and self.speaker_backend != "auto":
            return self.speaker_backend if shutil.which(self.speaker_backend) else ""
        for candidate in ("espeak-ng", "espeak", "spd-say"):
            if shutil.which(candidate):
                return candidate
        return ""

    def _detect_audio_player(self) -> str:
        if self.audio_player and self.audio_player != "auto":
            return self.audio_player if shutil.which(self.audio_player) else ""
        for candidate in ("mpg123", "ffplay", "mpv", "paplay", "aplay"):
            if shutil.which(candidate):
                return candidate
        return ""

    def enqueue_speech(self, text: str, *, category: str = "system") -> None:
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
        self._speaker_queue.put((category, cleaned))

    def _speaker_loop(self) -> None:
        while not self._audio_stop.is_set():
            try:
                category, text = self._speaker_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if not text:
                continue
            try:
                self._speak_text(text, category=category)
            except Exception as exc:
                self.get_logger().warn(f"Speaker playback failed: {exc}")
                self._publish_status(f"speaker_failed:{exc}")

    def _speak_text(self, text: str, *, category: str = "system") -> None:
        if category == "ai" and self.server_assistant_enabled and self.server_tts_enabled:
            try:
                self._speak_with_server_tts(text)
                self._publish_status("speaker_ai:server_tts")
                return
            except Exception as exc:
                self.get_logger().warn(f"Server TTS failed, using local fallback: {exc}")
                self._publish_status(f"speaker_ai_server_failed:{exc}")
                text = "AI 서버 음성 연결이 원활하지 않습니다."

        if category in {"system", "emergency"} and self._speak_system_sound(text):
            self._publish_status(f"speaker_{category}:prerecorded")
            return

        if self._speak_with_piper(text):
            self._publish_status(f"speaker_{category}:piper")
            return

        self._speak_with_local_backend(text)
        self._publish_status(f"speaker_{category}:local_tts")

    def _speak_with_server_tts(self, text: str) -> None:
        if not self._audio_player_command:
            raise RuntimeError("audio player is unavailable")
        response = requests.post(
            f"{self.buddybot_ai_url}/tts",
            json={"text": text},
            timeout=(2.0, self.server_tts_timeout_sec),
        )
        response.raise_for_status()
        media_type = response.headers.get("content-type", "").lower()
        suffix = ".wav" if "wav" in media_type else ".mp3"
        temp_path = self._write_temp_audio(response.content, suffix=suffix)
        try:
            self._play_audio_file(temp_path)
        finally:
            temp_path.unlink(missing_ok=True)

    def _speak_system_sound(self, text: str) -> bool:
        if self.system_sound_dir is None or not self._audio_player_command:
            return False
        sound_key = {
            "네.": "yes",
            "말씀하세요.": "ready",
            "전진.": "forward",
            "지속 전진.": "forward",
            "후진.": "backward",
            "왼쪽.": "strafe_left",
            "오른쪽.": "strafe_right",
            "좌회전.": "rotate_left",
            "우회전.": "rotate_right",
            "정지.": "stop",
            "추종 시작.": "follow_start",
            "추종 중지.": "follow_stop",
            "로컬 음성 명령만 사용할 수 있습니다.": "server_offline",
        }.get(text)
        if not sound_key:
            return False
        for suffix in (".wav", ".mp3"):
            path = self.system_sound_dir / f"{sound_key}{suffix}"
            if path.is_file():
                self._play_audio_file(path)
                return True
        return False

    def _speak_with_piper(self, text: str) -> bool:
        if not self.piper_model_path or not self._audio_player_command or shutil.which("piper") is None:
            return False
        temp_path = self._write_temp_audio(b"", suffix=".wav")
        try:
            completed = subprocess.run(
                ["piper", "--model", self.piper_model_path, "--output_file", str(temp_path)],
                input=text,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            if completed.returncode != 0:
                stderr = (completed.stderr or completed.stdout or "").strip()
                raise RuntimeError(stderr or f"piper exited with {completed.returncode}")
            self._play_audio_file(temp_path)
            return True
        finally:
            temp_path.unlink(missing_ok=True)

    @staticmethod
    def _write_temp_audio(payload: bytes, *, suffix: str) -> Path:
        fd, temp_name = tempfile.mkstemp(prefix="buddybot_audio_", suffix=suffix)
        os.close(fd)
        temp_path = Path(temp_name)
        temp_path.write_bytes(payload)
        return temp_path

    def _play_audio_file(self, path: Path) -> None:
        player = self._audio_player_command
        if not player:
            raise RuntimeError("audio player is unavailable")
        active_player = "aplay" if path.suffix.lower() == ".wav" and shutil.which("aplay") else player
        if active_player == "mpg123":
            command = [active_player, "-q", str(path)]
        elif active_player == "ffplay":
            command = [active_player, "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)]
        elif active_player == "mpv":
            command = [active_player, "--no-video", "--really-quiet", str(path)]
        elif active_player == "aplay":
            command = [active_player, "-q", str(path)]
        else:
            command = [active_player, str(path)]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        if completed.returncode != 0:
            stderr = (completed.stderr or completed.stdout or "").strip()
            raise RuntimeError(stderr or f"{active_player} exited with {completed.returncode}")

    def _speak_with_local_backend(self, text: str) -> None:
        backend = self._speaker_backend_command
        if not backend:
            raise RuntimeError("local TTS backend is unavailable")

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
            self._speaker_queue.put(("", ""))
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
