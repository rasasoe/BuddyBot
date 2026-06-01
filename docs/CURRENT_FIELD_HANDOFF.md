# BuddyBot Current Field Handoff

Last updated: 2026-05-18
Repo baseline: current working tree after follow-yaw/voice-mode update

## 2026-05-06 Fast Resume

Use `BuddyBot` as the main repo. `BuddyBot-ai` and `AMR` are references only unless the user explicitly switches scope.

Current field priority:
- User-following mode first.
- Checkpoint/local navigation is deprioritized because encoder odom exists but is not calibrated enough for reliable route driving yet.

Latest known-good direction:
- MobileNet-SSD v2 COCO is the preferred detector path.
- Expected model files on the Pi:
  - `~/BuddyBot/models/mobilenet_ssd_v2_coco.pb`
  - `~/BuddyBot/models/mobilenet_ssd_v2_coco.pbtxt`
- If detector is working, the panel camera should show a green detection box.
- Then press follow start from the camera toolbar and watch:
  - `/vision/person_bbox`
  - `/cmd_vel_follow`
  - `/cmd_vel_final`

Latest follow/manual motion baseline:
- Follow is now a lag-safe visual profile because the detector sees people but the live camera/control loop can fall behind real motion.
- Camera capture drains queued UVC frames before publishing:
  - `BUDDYBOT_CAMERA_DISCARD_BUFFERED_FRAMES=1`
  - `BUDDYBOT_CAMERA_OPENCV_THREADS=2`
  - `BUDDYBOT_DETECT_OPENCV_THREADS=2`
- Follow rotation is intentionally very slow because the camera/detector stream cannot support fast turning:
  - `BUDDYBOT_FOLLOW_CENTER_GAIN=0.00055`
  - `BUDDYBOT_FOLLOW_MAX_ANGULAR=0.045`
- Follow forward is now near the panel's 100% manual-forward feel, but still below the backend hard cap:
  - `BUDDYBOT_FOLLOW_HEIGHT_GAIN=0.010`
  - `BUDDYBOT_FOLLOW_TARGET_HEIGHT=1.16`
  - `BUDDYBOT_FOLLOW_MAX_LINEAR=0.42`
  - `BUDDYBOT_FOLLOW_MIN_LINEAR=0.34`
- Reverse is disabled in follow mode so stale close-range detections stop instead of making the robot back away from the user:
  - `BUDDYBOT_FOLLOW_ALLOW_REVERSE=0`
- Because C920/MobileNet can keep the person bbox nearly full-frame even when the user steps away, follow now has a visible-person forward push:
  - `BUDDYBOT_FOLLOW_VISIBLE_FORWARD=0.34`
  - `BUDDYBOT_FOLLOW_VISIBLE_FORWARD_CENTER_DEADZONE=120`
  - `BUDDYBOT_FOLLOW_VISIBLE_FORWARD_MAX_HEIGHT=1.10`
  - This keeps the robot moving forward slowly when the person is visible and roughly centered, while LiDAR avoidance still handles close obstacles.
- Follow forward now applies the same practical right-yaw trim direction used by manual forward, only while moving forward and the person is near center:
  - `BUDDYBOT_FOLLOW_FORWARD_YAW_TRIM=-0.05`
  - `BUDDYBOT_FOLLOW_FORWARD_YAW_TRIM_CENTER_DEADZONE=120`
  - This is intended to cancel the field-observed slight left drift during follow forward motion without changing manual drive.
- Near-field vision behavior:
  - turn suppression starts at bbox `area_ratio>=0.34` or `width_ratio>=0.50`
  - close anchor stop triggers at bbox `area_ratio>=0.56`, `width_ratio>=0.70`, or a top-line close anchor
  - this prevents the chassis from rotating the camera away from a close target.
- Detector target lock:
  - the detector prefers the previously tracked person for about 2s if another person appears elsewhere in frame.
  - if a new detection is too far from the locked target during that window, it is withheld instead of switching targets.
- Follow distance defaults back to camera bbox height, because corridor screenshots showed LiDAR distance gating could falsely block centered forward motion:
  - `BUDDYBOT_FOLLOW_USE_LIDAR_DISTANCE=0`
  - `BUDDYBOT_FOLLOW_HEIGHT_DEADZONE=16`
  - `BUDDYBOT_FOLLOW_TARGET_DISTANCE=0.95`
  - `BUDDYBOT_FOLLOW_DISTANCE_DEADZONE=0.18`
  - `BUDDYBOT_FOLLOW_MIN_DISTANCE=0.45`
  - LiDAR distance control can still be enabled for experiments, but default safety stays in `lidar_avoidance_node`.
- Follow now publishes a smoothed 10Hz command stream:
  - `BUDDYBOT_FOLLOW_COMMAND_RATE=10.0`
  - `BUDDYBOT_FOLLOW_LINEAR_ACCEL=0.55`
  - `BUDDYBOT_FOLLOW_ANGULAR_ACCEL=0.05`
- Follow bbox input is now filtered before velocity is computed:
  - `BUDDYBOT_FOLLOW_BBOX_SMOOTHING_ALPHA=0.45`
  - `BUDDYBOT_FOLLOW_BBOX_FILTER_RESET_SEC=0.9`
- Stale visual data is rejected before commanding motion:
  - `BUDDYBOT_FOLLOW_BBOX_TIMEOUT=2.5`
  - `BUDDYBOT_FOLLOW_MAX_SOURCE_AGE=0.0`
  - source age is reported in `/follow/status`, but default rejection is disabled because the Pi5 DNN path can exceed the first strict threshold and block all motion.
- Presentation mode now defaults to the old standalone-controller camera scale:
  - `BUDDYBOT_CAMERA_WIDTH=320`
  - `BUDDYBOT_CAMERA_HEIGHT=240`
  - `BUDDYBOT_CAMERA_FPS=10`
  - `BUDDYBOT_CAMERA_PUBLISH_RATE=10`
- Deadzone defaults are scaled from the old 160x120 follow controller to 320x240:
  - `BUDDYBOT_FOLLOW_CENTER_DEADZONE=50`
  - `BUDDYBOT_FOLLOW_HEIGHT_DEADZONE=16`
- Detector preprocessing matches the old TensorFlow SSD controller:
  - `scale_factor=1.0`
  - `mean_values=[0,0,0]`
- Detector accepts both repo model names and old standalone model names:
  - `mobilenet_ssd_v2_coco.pb` or `frozen_inference_graph.pb`
  - `mobilenet_ssd_v2_coco.pbtxt` or `ssd_mobilenet_v2_coco_2018_03_29.pbtxt`
- Follow controller publishes `/follow/status` for panel/debug diagnostics.
- `/follow/status.control_reason` and the panel follow note show why the current follow command was selected, for example `visible_forward_after_reverse_blocked`.
- Manual rotation profile:
  - `offset=0.096,gain=0.112`
- Manual strafe profile was restored because lateral movement felt too weak:
  - frontend `offset=0.26,gain=0.14`
  - backend `BUDDYBOT_MANUAL_STRAFE_LIMIT=0.46`

Latest voice-mode baseline:
- Presentation mode starts microphone listening, but robot voice command execution is gated off until the panel voice mode is turned on:
  - `BUDDYBOT_VOICE_COMMAND_ENABLED=0`
- The panel has a voice-mode selector:
  - `로컬 명령`: execute robot commands locally.
  - `서버컴 연동`: execute robot commands locally first, then send only unmatched/free conversation to `BUDDYBOT_AI_URL` / server URL.
- Supported local commands include examples such as:
  - `버디봇 전진`
  - `버디봇 정지`
  - `버디봇 사용자 추종`
  - `버디봇 주방 이동`
- The panel publishes voice runtime state to:
  - `/voice/enabled`
  - `/voice/assistant_enabled`
  - `/voice/server_url`

Why this matters:
- Previous follow behavior could pulse `forward -> stop -> forward` because follow commands were only published when bbox messages arrived.
- `command_mux_node` treats sources as stale after `0.5s`, so slow detector cadence could drop follow to idle between frames.
- `ef60ade` fixes that by letting bbox updates set the target velocity while the follow controller keeps publishing ramped commands at 10Hz.

Latest motion/Pico note:
- Replacement Pico was used after USB-C pad damage.
- New replacement-Pico field test showed gross forward/rotate/strafe mixing, so the current firmware trial baseline uses `MOTOR_DIRECTION_SIGNS["right"] = 1` and disables manual/follow yaw trim by default.
- If firmware is recopied, copy the full Pico firmware set, not only `main.py`.

Pi5 standard restart:

```bash
cd ~/BuddyBot
git pull origin main
cd ~/BuddyBot/software/pi5/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select buddybot_msgs buddybot_base buddybot_system buddybot_nav buddybot_panel buddybot_voice buddybot_vision
source install/setup.bash
cd ~/BuddyBot
bash scripts/start_presentation_mode.sh mapping
```

Fast rebuild after the latest follow/panel/voice change:

```bash
cd ~/BuddyBot
git pull origin main
cd ~/BuddyBot/software/pi5/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select buddybot_vision buddybot_panel buddybot_voice
source install/setup.bash
cd ~/BuddyBot
bash scripts/start_presentation_mode.sh mapping
```

If follow does not move, diagnose in this order:
1. Green bbox appears on panel camera.
2. `/vision/person_bbox` publishes.
3. `/cmd_vel_follow` publishes nonzero values after follow is enabled.
4. `/cmd_vel_final` selects follow and publishes nonzero values.
5. Pico status stays fresh and no safety/estop is active.
6. If `/cmd_vel_follow` pulses or drops out, inspect `follow_controller.log` and check that the latest build includes `command_rate_hz` and accel-limit logs.
7. If panel state is unclear, inspect `/follow/status` or `follow_status.log` from the debug bundle.

This is the fast resume page for a new laptop, a new Codex session, or the Pi5 field machine. Read this first, then use `AI_HANDOFF.md`, `docs/field_log.md`, and `docs/CODEX_RESUME_WORKFLOW.md` for deeper history.

## Current Working Baseline

- Manual driving is the best known hardware baseline so far. The user reported the robot moves very well after the Pico smoothing and manual-drive tuning work.
- Keep the current Pico motor mapping, wheel geometry, ramp limiting, and manual trim as the locked baseline unless a new single-wheel test proves otherwise.
- The panel manual pad is camera-first: front camera, manual arrows, then quick commands.
- Manual rotation speed was raised after field feedback, and right-turn commands receive a small boost to better match left-turn feel.
- Manual strafe was restored upward after the follow-speed tuning made lateral movement feel too weak from the panel.
- The minimap start button now means live LiDAR accumulation only. It should not make the robot wander automatically.
- Checkpoint motion does not require minimap start. It does require a live pose from `/odom` or `/amcl_pose`.

## Latest Field Change (2026-05-06)

Follow/manual motion tuning after live Pi5 tests:

Field sequence:
- Follow initially did not move because detection was missing or not reaching the panel.
- MobileNet-SSD setup, COCO person id, compatible BEST_EFFORT QoS, and debug-image camera overlay made detection visible.
- Follow then began moving, but rotation was too fast for camera cadence.
- First turn-rate reduction was too slow, so turn rates were restored to about 80% of the original aggressive baseline.
- Forward/backward follow motion was then reduced because the robot advanced faster than the camera/detector loop.
- Latest feedback showed stop/start pulsing and lurching, so follow command publication was changed to a smoothed 10Hz stream.

Current code expectation:
- `detector_node` publishes bbox/debug data.
- `follow_controller_node` stores bbox-derived target velocity.
- A command timer publishes ramped `/cmd_vel_follow` at 10Hz.
- `command_mux_node` should keep selecting follow while the ramped command is active.
- If bbox goes stale, follow ramps to zero instead of abruptly snapping to zero.

Recommended next field test:
1. Pull `main`.
2. Rebuild `buddybot_vision buddybot_panel`.
3. Start presentation mode.
4. Confirm green bbox on camera.
5. Press follow start from the camera toolbar.
6. Watch `/cmd_vel_follow`, `/cmd_vel_final`, and physical motion.

Primary tuning knobs, in order:
- Still lurching: lower `BUDDYBOT_FOLLOW_LINEAR_ACCEL`.
- Smooth but too slow forward: raise `BUDDYBOT_FOLLOW_MAX_LINEAR` slightly.
- Turns too fast: lower `BUDDYBOT_FOLLOW_CENTER_GAIN` slightly.
- Turns too weak: raise `BUDDYBOT_FOLLOW_CENTER_GAIN` slightly, but keep `BUDDYBOT_FOLLOW_MAX_ANGULAR` low unless field data clearly says otherwise.

## Previous Field Change (2026-05-04)

DNN 추종 불가 수정 + 패널 카메라에 검출 박스 표시.

**수정 내용:**
- `vision.launch.py`: `confidence_threshold` 0.5 → 0.2 (실내 환경 MobileNet-SSD v2 실제 검출 범위 반영)
- `vision.launch.py`: `publish_debug_image` True 활성화 (기본값 변경)
- `panel_server.py`: `/vision/person_bbox` 구독 QoS RELIABLE → BEST_EFFORT (detector 발행 QoS와 일치시킴)
- `panel_server.py`: `/vision/debug_image` 구독 추가 — 검출 bbox 오버레이 프레임을 패널 카메라 화면에 자동 표시
- `index.html`: camera-toolbar 2열 그리드로 재배열 (카메라닫기|추종시작 / 새로고침|추종끄기)

**QoS 수정 배경:**
ROS 2에서 BEST_EFFORT publisher + RELIABLE subscriber는 연결이 성립하지 않는다. `detector_node`가 BEST_EFFORT로 발행하는데 `panel_server`가 rclpy 기본값(RELIABLE)으로 구독하면 패널은 검출 결과를 절대 받지 못한다. 이 조합이 "person not detected" 고착 원인이었다.

**현장 검증 필요:**
패널 카메라 화면에 초록 박스가 뜨는지 확인. 박스가 뜨면 추종 정상 동작 기대.

---

## Previous Field Change

Manual LiDAR avoidance can now be toggled from the manual-control UI.

- Default: `수동 회피 OFF`
- OFF behavior: manual driving bypasses LiDAR avoidance for direct control feel.
- ON behavior: manual driving also uses LiDAR avoidance.
- Autonomous navigation and follow mode still use LiDAR avoidance regardless of the manual toggle.
- ROS topic: `/system/manual_avoidance_enabled`
- Panel API: `POST /api/manual-avoidance`

Checkpoint and route requests now wait briefly for `waypoint_manager` acknowledgement.

- If `waypoint_manager` receives the request, the panel should show a status like `navigating_local:<name>` or `navigating_nav2:<name>`.
- If the request is published but not acknowledged, the panel returns a visible error instead of silently pretending success.
- Command QoS between panel and waypoint manager is now reliable + volatile to avoid the previous command-topic mismatch.

## Current Known Navigation Blocker

Current state:
- `/odom` now exists through `buddybot_base.encoder_odom_node`.
- The previous `pose_unavailable` blocker was cleared in field testing: panel status showed `pose_available: true` and `pico_connected: true`.
- Checkpoint driving is still deprioritized because local encoder odom is not calibrated enough yet. Field tests showed strong spinning before final-yaw alignment was disabled, then triangular/unstable movement on farther goals.
- Treat encoder odom as good enough for pose availability and short diagnostic tests, not yet good enough for reliable route driving.

Historical path to this state:

Checkpoint move previously stopped at:

```text
pose가 잡힌 뒤 다시 실행하세요
```

Meaning: the panel has not received `/odom` or `/amcl_pose` yet.

Important finding: this repository currently subscribes to `/odom`, but no node in the repo appears to publish `/odom`.

Observed subscriptions:

- `buddybot_panel/panel_server.py` subscribes to `/odom` and `/amcl_pose`
- `buddybot_nav/waypoint_manager_node.py` subscribes to `/odom` and `/amcl_pose`

Observed gap:

- No current Python node in `software/pi5/ros2_ws/src` publishes `nav_msgs/Odometry` on `/odom`.

Local implementation now added:

- Pico firmware now includes cumulative left/right/back encoder counts in `STAT`.
- `pico_bridge_node` parses those counts into `buddybot_msgs/Status`.
- New `buddybot_base encoder_odom_node` subscribes to `/buddybot/pico_status`.
- It publishes `nav_msgs/Odometry` on `/odom`.
- It also publishes `odom -> base_link` TF by default.
- `scripts/start_mapping_panel.sh` starts `encoder_odom_node` after `pico_bridge`.

If returning to checkpoint/local navigation on the Pi:

- Keep the current Pico firmware baseline unless a new firmware change is made.
- Rebuild `buddybot_base` if encoder odom code or dependencies changed.
- Verify `/buddybot/pico_status` has changing encoder counts while driving.
- Verify `/odom` publishes and has the expected sign/scale while manually driving.
- Tune encoder signs/scale and local navigation gains before trusting checkpoint movement again.

## Pi5 Field Commands

Use `python3`, not `python`, on the Pi.

Check panel status:

```bash
curl -s http://127.0.0.1:8090/api/status | python3 -m json.tool
```

Check pose topics:

```bash
source /opt/ros/jazzy/setup.bash
source ~/BuddyBot/software/pi5/ros2_ws/install/setup.bash
ros2 topic echo --once /odom
ros2 topic echo --once /amcl_pose
```

If both commands hang or show no message after rebuilding and recopying Pico firmware, checkpoint navigation cannot start yet because pose is still missing.

Check whether the Pico bridge is publishing encoder status:

```bash
ros2 topic echo --once /buddybot/pico_status
```

Check navigation acknowledgements:

```bash
ros2 topic echo /nav/navigation_status
```

Check command arbitration:

```bash
ros2 topic echo /system/command_status
ros2 topic echo /cmd_vel_final
```

## Pi5 Pull, Build, Run

```bash
cd ~/BuddyBot
git pull origin main

cd ~/BuddyBot/software/pi5/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select \
  buddybot_msgs \
  buddybot_base \
  buddybot_system \
  buddybot_nav \
  buddybot_panel \
  buddybot_voice \
  buddybot_vision
source install/setup.bash

cd ~/BuddyBot
bash scripts/start_presentation_mode.sh mapping
```

## Pico Firmware Reminder

The 2026-05-04 encoder odometry change requires Pico firmware recopy because `STAT` now carries encoder counts.

If the Pi has not received the known good Pico baseline yet, copy these before running ROS:

```bash
cd ~/BuddyBot
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/config.py :config.py
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/pins.py :pins.py
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/kinematics.py :kinematics.py
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/motor_driver.py :motor_driver.py
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/encoder.py :encoder.py
mpremote connect /dev/ttyACM0 fs cp firmware/pico_motor_controller/main.py :main.py
mpremote connect /dev/ttyACM0 reset
```

Do not use `mpremote fs cp` while ROS is actively using the Pico serial port.

## What To Verify Next

1. Pull `main` on the Pi and rebuild:

```bash
cd ~/BuddyBot && git pull origin main
cd software/pi5/ros2_ws && source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select buddybot_vision buddybot_panel
source install/setup.bash
cd ~/BuddyBot && bash scripts/start_presentation_mode.sh mapping
```

2. **추종 검증 (최우선):** 패널 카메라 화면에 초록 박스 확인.
   - 박스 뜸 → 추종 시작 눌러 로봇 이동 확인
   - 박스 안 뜸 → 모델 파일 경로 확인:
     ```bash
     ros2 run buddybot_vision detector_node --ros-args --log-level info 2>&1 | grep -E "model_config|model_weights"
     ```

3. 수동 회피 상태 확인: 패널 `수동 회피 OFF` 표시.
4. 기본 상태 점검:

```bash
curl -s http://127.0.0.1:8090/api/status | python3 -m json.tool
ros2 topic echo --once /buddybot/pico_status
ros2 topic echo --once /odom
```

5. `/odom` 없으면 `encoder_odom.log` 확인 및 `buddybot_base` 재빌드 필요.

## Next Coding Task

Field-test `/odom` from Pico encoder feedback.

Suggested scope:

- Confirm encoder count signs and scale on hardware.
- Tune `encoder_odom_node` parameters if odom direction is inverted:
  - `left_encoder_sign`
  - `right_encoder_sign`
  - `back_encoder_sign`
  - `rotation_radius_m`
- Retry short local checkpoint movement.
- Update this document and `docs/field_log.md` after field validation.

## 2026-05-27 Current Field Delta

Latest field state:
- Replacement Pico firmware is online and manual direction mapping is now correct.
- Remaining field symptoms were steady-drive stutter, slight left drift during forward motion, and STT confusion between short Korean commands.

Latest code changes:
- Pico firmware motor PID correction is disabled by default (`PID_KP=0.0`, `PID_CORR_MAX=0.0`) to avoid encoder-noise pulsing during steady manual drive.
- Default forward yaw trim is now `-0.03` for panel manual forward, voice forward, and follow forward.
- Voice command policy now treats plain `BuddyBot forward` as continuous forward.
- Voice continuous max default is `0.0`, meaning it keeps moving until panel stop, voice stop, safety, or process shutdown.
- Stop aliases were expanded; recommend using `멈춰`, `스톱`, or `그만` in the field instead of relying on `정지`.

Important STT note:
- Current voice recognition backend is online Google Web Speech through Python `speech_recognition`.
- It is not an onboard/offline Google model. Local control happens after the recognized text returns to the Pi.

Required Pi update:

```bash
cd ~/BuddyBot
git pull origin main
bash scripts/flash_pico.sh
cd software/pi5/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select buddybot_voice buddybot_panel
source install/setup.bash
cd ~/BuddyBot
BUDDYBOT_FORCE_LIDAR_START=1 bash scripts/start_presentation_mode.sh mapping
```

Correction after field test:
- The `-0.03` trim was too aggressive and caused hard right drift.
- Open-loop Pico drive increased pulsing.
- Latest code keeps continuous `BuddyBot forward`, but restores Pico P-only correction and resets all default forward yaw trims to `0.0`.
- If a small left drift remains, test runtime trim in tiny steps, for example `-0.005`.

Latest follow-up:
- Zero trim still left-drifts slightly, and forward still pauses/resumes.
- Current code now uses tiny trim `-0.006`, softer Pico P correction (`PID_KP=0.12`, `PID_CORR_MAX=0.12`), a 2.0s Pico watchdog, 2.0s command mux timeout, 3.0s panel hold timeout, 250ms panel manual refresh, and 50ms voice manual publishing.
- Pico must be reflashed again for this change.

Manual stutter root cause and latest fix:
- Follow was smooth while panel manual stuttered, so the remaining stutter was isolated to `/cmd_vel_manual`.
- Panel held-button refreshes were publishing `/voice/manual_override` every 250 ms.
- `buddybot_voice` responded to each override with a zero burst on `/cmd_vel_manual`, fighting the panel manual command.
- Latest code sends panel manual override only on start/stop/direction change.
- `buddybot_voice` now sends a zero burst on manual override only when a voice-started manual motion was active.
- Pico reflash is not required for this latest patch; rebuild `buddybot_voice` and `buddybot_panel` only.

## 2026-06-01 Manual baseline and trim follow-up

- Panel manual 100% forward/backward now matches the previous 150% slider feel:
  - forward `0.46`
  - backward `0.435`
- Voice manual speed default is now `0.46`.
- Small manual/voice yaw trims compensate residual field drift:
  - forward `-0.003`
  - backward `-0.003`
  - strafe left `0.003`
  - strafe right `-0.003`
- Follow tuning was intentionally left unchanged because follow behavior is smooth.
- This update only needs `buddybot_voice` and `buddybot_panel` rebuilds; Pico reflash is not required.

## 2026-06-01 Hybrid TTS routing

- AI conversation answers now use the existing BuddyBot-ai `POST /tts` route and play the returned Edge TTS audio on the Pi.
- Short system and emergency responses stay local on the Pi so server latency or outages do not block robot feedback.
- Local speech priority:
  1. optional prerecorded WAV/MP3 files in `buddybot_voice/assets/system_sounds`
  2. optional Piper model when configured
  3. existing `espeak-ng` fallback
- Stop processing remains local-first: motion is cleared before the emergency speech response is queued.
- Install `mpg123` on the Pi for server MP3 playback.
- This update only needs a `buddybot_voice` rebuild. Pico reflash is not required.

## 2026-06-01 Hybrid Whisper STT routing

- Default Pi recognition backend is now `hybrid`.
- Waiting for wake-word:
  - Pi local `faster-whisper` tiny first.
- After wake-word:
  - BuddyBot-ai `POST /stt` server Whisper first.
  - Pi local `faster-whisper` tiny fallback.
  - Optional Google Web Speech fallback last.
- While moving or following:
  - Pi local tiny checks emergency stop first so `stop` does not wait for the network.
- A failed server STT call starts a 10s cooldown so repeated network failures do not stall the microphone loop.
- Run `bash scripts/setup_pi5_whisper.sh` once on the Pi to install `faster-whisper` and preload the tiny model.
- Rebuild `buddybot_voice` and `buddybot_panel`. Pico reflash is not required.
