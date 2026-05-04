# BuddyBot Current Field Handoff

Last updated: 2026-05-04
Repo baseline: `9422dea` (`fix: lower DNN threshold to 0.2, show detection bbox on camera feed`)

This is the fast resume page for a new laptop, a new Codex session, or the Pi5 field machine. Read this first, then use `AI_HANDOFF.md`, `docs/field_log.md`, and `docs/CODEX_RESUME_WORKFLOW.md` for deeper history.

## Current Working Baseline

- Manual driving is the best known hardware baseline so far. The user reported the robot moves very well after the Pico smoothing and manual-drive tuning work.
- Keep the current Pico motor mapping, wheel geometry, ramp limiting, and manual trim as the locked baseline unless a new single-wheel test proves otherwise.
- The panel manual pad is camera-first: front camera, manual arrows, then quick commands.
- Manual rotation speed was raised after field feedback, and right-turn commands receive a small boost to better match left-turn feel.
- The minimap start button now means live LiDAR accumulation only. It should not make the robot wander automatically.
- Checkpoint motion does not require minimap start. It does require a live pose from `/odom` or `/amcl_pose`.

## Latest Field Change (2026-05-04)

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

## Current Known Blocker

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

Still required on the Pi:

- Recopy Pico firmware files before testing encoder odom.
- Rebuild `buddybot_base` so the new console script and dependencies are installed.
- Verify `/buddybot/pico_status` has changing encoder counts while driving.
- Verify `/odom` publishes and checkpoint navigation leaves `pose_unavailable`.

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
