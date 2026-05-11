# BuddyBot AI Handoff

## 2026-05-06 Resume Snapshot

Current repo baseline: current `main` (`Make follow lag-safe for slow camera`).

Current practical priority:
- Focus on user-following mode first.
- Checkpoint/local navigation has `/odom` now, but encoder odom is not field-calibrated enough for reliable checkpoint driving; it previously traced triangular/unstable paths.
- Follow mode is the more promising demo path because it depends mostly on camera detection, follow controller, command mux, Pico bridge, and manual-safe stopping.

Latest follow-mode state:
- MobileNet-SSD v2 COCO model path is expected at:
  - `~/BuddyBot/models/mobilenet_ssd_v2_coco.pb`
  - `~/BuddyBot/models/mobilenet_ssd_v2_coco.pbtxt`
- `detector_node` default `person_class_id` is corrected to COCO person id `1`.
- DNN threshold is lowered for indoor detections.
- Detector has HOG/cascade fallback and diagnostic logging.
- Panel subscribes to bbox/debug image with compatible BEST_EFFORT QoS and shows detection boxes on the camera feed when available.
- Follow controller is now tuned for lag-safe camera tracking because person detection is good but live control can trail the camera:
  - presentation camera defaults: `320x240 @ 10fps`
  - `discard_buffered_frames=1`
  - camera/detector `opencv_threads=2`
  - `center_x_gain=0.0012`
  - `max_angular_velocity=0.10`
  - `height_gain=0.0035`
  - `target_height_ratio=0.60`
  - `max_linear_velocity=0.16`
  - `min_linear_velocity=0.10`
  - `deadzone_center=50`
  - `deadzone_height=30`
  - `bbox_timeout_sec=2.5` from presentation mode
  - `max_source_age_sec=0.0`
  - `allow_reverse=false`
  - `visible_forward_velocity=0.08`
  - `visible_forward_center_deadzone=120`
  - `use_lidar_distance=false`
  - `target_distance_m=0.95`
  - `distance_deadzone_m=0.18`
  - `min_follow_distance_m=0.45`
  - `command_rate_hz=10.0`
  - `linear_accel_limit=0.12/s`
  - `angular_accel_limit=0.12/s`
- Important behavior change: bbox callbacks now update a target command, and a 10Hz command timer ramps current velocity toward that target. This avoids follow mode pulsing `forward -> stop -> forward` when detector updates are slower than command_mux timeout.
- BBox input is now low-pass filtered before velocity is computed:
  - `bbox_smoothing_alpha=0.25`
  - `bbox_filter_reset_sec=0.9`
- Detector appends source image age to `/vision/person_bbox`; follow reports it in `/follow/status`.
- Source-age rejection is disabled by default after field feedback showed it could block all motion on the Pi5 DNN path.
- If C920/MobileNet returns a saturated/full-frame person bbox, follow no longer relies only on bbox height. It creeps forward slowly while the person is visible and roughly centered, with LiDAR avoidance responsible for stopping if the person is actually too close.
- LiDAR distance control exists but is disabled by default after corridor screenshots showed centered forward motion could be falsely blocked. Default follow distance is camera-height based, with LiDAR still active as a separate avoidance/safety override.
- `follow_controller_node` publishes `/follow/status` JSON diagnostics for panel and debug bundles.
- Detector preprocessing now matches the old TensorFlow SSD path:
  - `scale_factor=1.0`
  - `mean_values=[0,0,0]`
- Detector model resolution/path aliases accept both repo names and old standalone names:
  - `mobilenet_ssd_v2_coco.pb` or `frozen_inference_graph.pb`
  - `mobilenet_ssd_v2_coco.pbtxt` or `ssd_mobilenet_v2_coco_2018_03_29.pbtxt`
- Camera toolbar now has follow start/stop next to camera controls.
- Manual rotation is about 80% of the original aggressive baseline:
  - panel rotate profile `offset=0.096,gain=0.112`
- Manual strafe was restored after it felt too weak:
  - panel strafe profile `offset=0.26,gain=0.14`
  - backend `BUDDYBOT_MANUAL_STRAFE_LIMIT=0.46`

Latest Pico/motion state:
- A replacement Pico was brought back up and BuddyBot firmware was copied.
- `MOTOR_DIRECTION_SIGNS["right"] = -1` is the latest field-corrected baseline.
- If Pico firmware is recopied, include all firmware modules, especially `config.py`, `uart_protocol.py`, and `main.py`.

Recommended Pi5 resume command after pulling latest:

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

High-signal follow checks:

```bash
source /opt/ros/jazzy/setup.bash
source ~/BuddyBot/software/pi5/ros2_ws/install/setup.bash
ros2 topic echo /vision/detector_status
ros2 topic echo /vision/person_bbox
ros2 topic echo /follow/status
ros2 topic echo /cmd_vel_follow
ros2 topic echo /cmd_vel_final
tail -n 120 ~/BuddyBot/software/pi5/ros2_ws/log/mapping_panel/detector.log
tail -n 120 ~/BuddyBot/software/pi5/ros2_ws/log/mapping_panel/follow_controller.log
```

Do not reopen checkpoint odom/local navigation until follow mode is field-tested again. Current checkpoint/local nav has live `/odom`, but encoder scale/sign/frame calibration is still not trustworthy enough for route driving.

## 2026-05-06 Follow Tuning Timeline

Recent commits, newest last:

- `0ebe8f6` softened follow/manual turn rates after the camera could not keep up.
- `dbade25` restored turn rates to about 80% of the original baseline because the first reduction was too slow.
- `ffbdbb4` reduced follow forward/backward aggression after the robot advanced faster than the camera loop.
- `ef60ade` changed follow to a smoothed 10Hz command stream and restored manual strafe speed.

Current field expectation:
- Person box should appear first on the panel camera.
- Press follow start from the camera toolbar.
- The robot should start more gradually, keep command output alive between detector frames, and stop/ramp down when bbox becomes stale.
- If it still lurches, tune `BUDDYBOT_FOLLOW_LINEAR_ACCEL` downward first.
- If it follows too lazily but smoothly, tune `BUDDYBOT_FOLLOW_MAX_LINEAR` upward slightly before touching angular values.

## Start Here First

For the latest cross-environment resume state, read:

- `docs/CURRENT_FIELD_HANDOFF.md`
- `docs/CODEX_RESUME_WORKFLOW.md`
- latest entries in `docs/field_log.md`

The older checkpoint blocker was missing pose. That is no longer the main blocker: `buddybot_base.encoder_odom_node` now publishes `/odom` from Pico encoder status. The current navigation risk is calibration quality, not topic absence. Field tests showed checkpoint motion can spin or trace unstable triangular paths, so keep checkpoint/local navigation deprioritized until follow mode is field-tested again.

## Current State

BuddyBot is in a usable Pi5-only demo state, but the latest field work confirmed that the remaining instability is mostly around USB/power behavior on the real robot rather than a single ROS logic bug.

What is now fixed in code:
- Manual control in the panel is toggle-based and no longer drops out just because minimap stop logic ran while minimap was already idle.
- `scripts/start_all_pi5.sh` now refuses to start with a half-built workspace and prints the exact `colcon build --packages-select ...` command needed to recover.
- Camera FPS and publish-rate environment variables are normalized to ROS `double` parameters, so `BUDDYBOT_CAMERA_FPS=10` no longer crashes the camera node with a type mismatch.
- `scripts/run_demo_debug_bundle.sh` now reliably produces a post-run log bundle on shutdown instead of skipping cleanup.
- Camera launch scripts now support lower-bandwidth USB settings:
  - `BUDDYBOT_CAMERA_PIXEL_FORMAT`
  - `BUDDYBOT_CAMERA_BUFFER_SIZE`
- Presentation-mode launcher exists:
  - `scripts/start_presentation_mode.sh`
- Presentation-mode launcher now also lowers detector load:
  - `BUDDYBOT_DETECT_INTERVAL`
  - `BUDDYBOT_DETECT_CONFIDENCE`
  - `BUDDYBOT_DETECT_HOG_RESIZE_WIDTH`
  - `BUDDYBOT_DETECT_ALLOW_HOG_FALLBACK`
- Panel UI was cleaned up for field use:
  - Pico status shows more useful live values
  - minimap buttons and camera button layout were adjusted for mobile/demo use

What is still not fully solved in software:
- Real Pi5 field logs still show undervoltage warnings and USB reconnect events.
- Pico sometimes disappears briefly from USB and `pico_bridge` logs `device reports readiness to read but returned no data`.
- C920 can still disappear during long runs even when preflight passes.

## Confirmed Root Causes

### 1. Manual drive dropout

This one was a real code bug and is fixed.

Root cause:
- panel manual commands called minimap stop as a guard
- minimap stop unconditionally cleared manual motion
- the frontend was posting repeated `/api/manual`
- `command_mux` kept flipping between `manual` and `idle`

Relevant fix:
- [software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/panel_server.py](software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/panel_server.py)

Expected behavior now:
- panel manual buttons are toggle-style
- manual motion keeps publishing while active
- minimap idle state no longer injects a zero manual command

### 2. Camera param type mismatch

This one was also a code/script bug and is fixed.

Root cause:
- camera node declares `fps` and `publish_rate` as ROS doubles
- shell launchers sometimes passed plain integers like `10`
- ROS rejected the parameter type

Relevant fixes:
- [scripts/check_all_devices.sh](scripts/check_all_devices.sh)
- [scripts/start_mapping_panel.sh](scripts/start_mapping_panel.sh)
- [scripts/start_offline_demo.sh](scripts/start_offline_demo.sh)

### 3. Camera + LiDAR + Pico instability

This is only partially mitigated in software.

What logs proved:
- preflight can pass all three together
- later in the run, kernel logs can still show:
  - `Undervoltage detected!`
  - `USB disconnect`
  - `can't set config #1, error -71`
- `pico_bridge` can continue heartbeating and then suddenly report serial read failures
- camera can re-enter repeated reopen loops after initially coming up fine

Conclusion:
- this is not just a ROS graph issue
- this is not just a topic/QoS issue
- this is a field hardware stability issue with software mitigations layered on top

## Recommended Build After Pull

Use this on Pi5 after any meaningful pull:

```bash
cd ~/BuddyBot/software/pi5/ros2_ws
source /opt/ros/jazzy/setup.bash
rm -rf build install log
colcon build --symlink-install --packages-select \
  buddybot_msgs \
  buddybot_base \
  buddybot_system \
  buddybot_nav \
  buddybot_panel \
  buddybot_voice \
  buddybot_vision
source install/setup.bash
```

## Cross-Laptop Resume Rule

If work moves to another laptop or another Codex session, do not re-explain everything from scratch.

Use this repo workflow instead:
- read `AI_HANDOFF.md`
- read the latest dated section in `docs/field_log.md`
- read `docs/CODEX_RESUME_WORKFLOW.md`
- then have the new session summarize current state before doing anything else

This is now the expected handoff path for BuddyBot field debugging.

## Recommended Demo Start

### Normal full-stack start

```bash
cd ~/BuddyBot
bash scripts/start_all_pi5.sh mapping
```

### Presentation / unstable USB mode

Use this when the robot must demo now and hardware changes are not possible:

```bash
cd ~/BuddyBot
bash scripts/start_presentation_mode.sh mapping
```

What presentation mode changes by default:
- skips preflight re-open churn
- enables microphone listener for voice demos
- enables Pi speaker output path but clamps output volume to 35%
- keeps camera at the demo-safe full-feature profile
- keeps MJPG + small buffer
- keeps detector fallback workload within the Pi 5 USB/power budget
- aligns camera/debug topic checks with BEST_EFFORT image transport
- still runs through `run_demo_debug_bundle.sh` so shutdown produces logs automatically

## Recommended Runtime Knobs

Current full-function demo defaults:

```bash
BUDDYBOT_CAMERA_WIDTH=320
BUDDYBOT_CAMERA_HEIGHT=240
BUDDYBOT_CAMERA_FPS=15
BUDDYBOT_CAMERA_PUBLISH_RATE=15
BUDDYBOT_CAMERA_PIXEL_FORMAT=MJPG
BUDDYBOT_CAMERA_BUFFER_SIZE=1
BUDDYBOT_DETECT_INTERVAL=5
BUDDYBOT_DETECT_HOG_RESIZE_WIDTH=320
BUDDYBOT_ENABLE_MIC_LISTENER=1
BUDDYBOT_ENABLE_PI_SPEAKER=1
BUDDYBOT_SPEAKER_VOLUME_PERCENT=35
```

If camera and LiDAR barely coexist, lower from there rather than starting from a heavier profile.

If the camera is not required for the current demo slice:

```bash
BUDDYBOT_DISABLE_CAMERA=1 bash scripts/start_all_pi5.sh mapping
```

## Debug Bundle Workflow

Preferred reproduction command on Pi5:

```bash
cd ~/BuddyBot
bash scripts/start_presentation_mode.sh mapping
```

After reproducing, press `Ctrl+C` once and inspect the newest bundle:

```bash
BUNDLE_DIR="$(ls -dt /tmp/buddybot-debug-* | grep -v '\.tar\.gz$' | head -n 1)"
echo "$BUNDLE_DIR"
tail -n 80 "$BUNDLE_DIR/cmd_vel_manual.log"
tail -n 80 "$BUNDLE_DIR/cmd_vel_final.log"
tail -n 80 "$BUNDLE_DIR/pico_status.log"
tail -n 120 "$BUNDLE_DIR/command_mux.tail.log"
tail -n 120 "$BUNDLE_DIR/pico_bridge.tail.log"
tail -n 120 "$BUNDLE_DIR/camera.tail.log"
grep -n "Undervoltage\\|USB disconnect\\|error -71" "$BUNDLE_DIR/system_snapshot.log" | tail -n 40
```

How to read it quickly:
- `cmd_vel_manual.log`: panel/manual command publication
- `cmd_vel_final.log`: mux output that should actually reach the base
- `pico_status.log`: whether Pico status stayed alive
- `command_mux.tail.log`: manual vs idle flapping, source priority changes
- `pico_bridge.tail.log`: serial disconnect/read failure evidence
- `camera.tail.log`: camera reopen loop or parameter/open errors
- `system_snapshot.log`: kernel undervoltage / USB disconnect evidence

## High-Signal Files

- [scripts/start_presentation_mode.sh](scripts/start_presentation_mode.sh)
- [scripts/run_demo_debug_bundle.sh](scripts/run_demo_debug_bundle.sh)
- [scripts/start_all_pi5.sh](scripts/start_all_pi5.sh)
- [scripts/start_mapping_panel.sh](scripts/start_mapping_panel.sh)
- [scripts/start_offline_demo.sh](scripts/start_offline_demo.sh)
- [software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/panel_server.py](software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/panel_server.py)
- [software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/static/index.html](software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/static/index.html)
- [software/pi5/ros2_ws/src/buddybot_vision/buddybot_vision/camera_node.py](software/pi5/ros2_ws/src/buddybot_vision/buddybot_vision/camera_node.py)
- [docs/field_log.md](docs/field_log.md)

## Known Residual Risks

- If kernel logs show undervoltage and USB reconnects, no ROS patch can guarantee a clean long demo.
- If Pico disappears from USB, `pico_bridge` cannot recover movement by itself.
- If C920 vanishes from `lsusb` or `v4l2-ctl --list-devices`, treat it as hardware/runtime instability first, not a detector-node bug.
- `command_mux` and `camera_node` still print shutdown-time ROS context errors during forced stop; these are noisy but secondary compared to the real USB instability.

## Next AI Priority

1. Preserve the current presentation path; do not regress manual toggle control.
2. Keep documentation and launch commands aligned with the current package set.
3. If new logs still show USB drops, bias toward reducing runtime load rather than adding more background nodes.
4. Treat kernel undervoltage and USB disconnect evidence as first-class signals in any future diagnosis.

## Latest Motion Fix Direction

- Commit flow to remember:
  - `78a7db3`
    - restored the legacy standalone-style Pico control baseline
    - this is the point where gross `forward/backward` heading started matching the user's intended direction again
    - residual issue at that stage was a rightward steering bias
  - `ba4186b` and follow-up documentation commits
    - moved the behavior away from the earlier rightward bias
    - the robot is now closer to the intended heading overall, but the residual bias flipped to a slight left drift
  - Current interpretation:
    - keep the post-`78a7db3` overall direction baseline
    - do not reopen the full geometry/remap problem
    - only tune the remaining slight left drift
- User-facing symptom:
  - gross `forward/backward` direction is now finally close to the intended heading on hardware.
  - the remaining issue is smaller: both `forward` and `backward` still drift slightly to the left, so the robot traces a shallow arc.
- Current conclusion:
  - The gross motion direction should now be treated as fixed baseline, not reopened.
  - The next step is only a small steering-bias correction.
  - Do not revisit wheel geometry, wheel naming, or the legacy direct-mix structure unless a new single-wheel hardware test proves the baseline itself wrong.
- Current fix set:
  - `firmware/pico_motor_controller/config.py`
    - keep `MOTOR_DIRECTION_SIGNS` at `1/1/1`
    - keep the legacy standalone baseline:
      - `ENCODER_CPR = 11`
      - `GEAR_RATIO = 270`
      - `PID_KP = 0.3`
  - `firmware/pico_motor_controller/kinematics.py`
    - keep the legacy direct wheel mix:
      - `left = vx + 0.5 * vy + w`
      - `right = -vx + 0.5 * vy + w`
      - `back = -vy + w`
    - for pure `forward/backward`, the current intended behavior is `back ~= 0`
  - `firmware/pico_motor_controller/test_kinematics.py`
    - updated to reflect the legacy direct-mix expectation and passing locally
  - `firmware/pico_motor_controller/pins.py`
    - keep the January channel mapping:
      - `left = m0`
      - `right = m1`
      - `back = m2`
  - `firmware/pico_motor_controller/motor_driver.py`
    - keep the legacy polarity convention:
      - `+speed -> in1=0, in2=1`
      - `-speed -> in1=1, in2=0`
  - `firmware/pico_motor_controller/encoder.py`
    - keep the legacy encoder sign convention:
      - `enc_b == 0 -> +count`
      - `enc_b == 1 -> -count`
  - `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/static/index.html`
    - keep manual default speed conservative for indoor testing
      - slider default `60%`
      - lower base speeds than the original 100% profile
- Important operating note:
  - Treat the above Pico baseline as the locked reference configuration for all future workspaces.
  - If motion regresses, first verify `pins.py`, `motor_driver.py`, `encoder.py`, `kinematics.py`, `main.py`, and `config.py` still match this baseline before changing geometry again.
  - The remaining symptom to tune is:
    - `forward` drifts slightly left
    - `backward` drifts slightly left
  - This means future changes should bias toward tiny left/right correction only, not another full remap.
- Pi deployment reminder:
  - after pulling, re-copy at least:
    - `firmware/pico_motor_controller/config.py`
    - `firmware/pico_motor_controller/pins.py`
    - `firmware/pico_motor_controller/kinematics.py`
    - `firmware/pico_motor_controller/motor_driver.py`
    - `firmware/pico_motor_controller/encoder.py`
    - `firmware/pico_motor_controller/main.py`
  - then `mpremote ... reset`
  - then start ROS
  - do not use `mpremote fs cat/cp` while ROS is running
- Immediate resume test on Pi:
  - `git pull origin main`
  - copy `config.py`, `pins.py`, `kinematics.py`, `motor_driver.py`, `encoder.py`, `main.py` to Pico
  - `mpremote ... reset`
  - `bash scripts/start_presentation_mode.sh mapping`
  - verify `forward`, `backward`, `rotate_left`, `rotate_right`, `stop`
  - treat any new failure as a regression from this baseline unless single-wheel tests prove otherwise

## 2026-04-27 Validation Snapshot

- Field result:
  - The user explicitly reported that the robot now moves very well on hardware.
  - Treat the current motion stack as the best known live-demo baseline, not as another temporary experiment.
- What this means operationally:
  - Do not reopen full wheel-geometry or sign-remap work unless a brand-new hardware regression proves this baseline wrong.
  - Prefer tiny tuning only.
  - Preserve the current manual-drive feel, avoidance behavior, and Pico output smoothing unless a concrete new failure appears.

## 2026-04-27 UI Follow-up

- Final UI request from the user after the successful field test:
  - keep the manual arrow control block directly below `전방 카메라`
  - keep it above `빠른 명령`
- Why:
  - this is the most practical operator flow during demos:
    - open camera
    - see robot response live
    - drive immediately from the arrow pad
- Source file:
  - `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/static/index.html`

## Documentation Rule Going Forward

- If the user says a hardware baseline is finally working well, record that fact in both:
  - `docs/field_log.md`
  - `AI_HANDOFF.md`
- Do not only log code deltas.
- Also log the user-observed quality signal:
  - "moves well"
  - "good for field demo"
  - "treat as locked baseline until a real regression appears"

## 2026-04-27 Live Minimap + Checkpoint Follow-up

- New field request after the stable motion baseline:
  - right turns still felt slower than left turns
  - pressing `미니맵 생성` should not make the robot wander on its own
  - checkpoints must be reachable during live LiDAR operation, not only after a separate map-building phase
- Implementation direction locked in:
  - panel manual `rotate_right` now gets a small boost to match left-turn feel
  - local checkpoint navigation also boosts negative angular commands slightly for the same chassis asymmetry
  - minimap start now means "begin live LiDAR accumulation" instead of "autonomous roaming"
  - manual drive, waypoint go, destination go, and route run no longer shut the live minimap off
  - waypoint manager now reloads the waypoint YAML from disk on navigation requests and honors `BUDDYBOT_WAYPOINT_FILE`
  - when pose source is not `amcl`, checkpoint go should prefer local navigation immediately
- Operational expectation on Pi:
  - in live presentation mode, the operator can start the minimap, drive manually or press checkpoint go, and watch the map keep updating without autonomous sweep behavior

## 2026-04-28 Checkpoint UI Cleanup

- Follow-up request from the user:
  - checkpoint move should not feel coupled to the minimap start button
  - the minimap/checkpoint area had too many duplicated buttons and felt visually noisy
  - left/right rotate buttons still felt too slow for manual driving
- What changed:
  - manual rotate speed was increased in the panel speed profile and panel-side angular cap defaults
  - `/api/go`, `/api/destinations/go`, and ad-hoc route run now fail loudly when pose or ROS navigation publishers are missing instead of pretending success
  - waypoint navigation in `waypoint_manager_node.py` no longer cancels just because the system mode is `IDLE`; only explicit `MANUAL` or `FOLLOW` mode changes cancel it
  - the minimap card now states clearly that checkpoint movement does not require minimap start
  - the checkpoint UI was simplified into three grouped areas:
    - checkpoint move
    - checkpoint save
    - route builder
  - the saved checkpoint list is now selection-focused with only one inline action (`경로에 추가`) instead of stacked move/delete buttons on every row
## 2026-05-04 DNN 추종 불가 수정 + 패널 검출 박스

문제:
- `추종 시작` 버튼을 눌러도 로봇이 움직이지 않음
- 패널 "person not detected" 고정, 검출기는 "DNN 준비" 정상 표시
- 카메라 앞에 사람이 서있는 것 실물 확인

확인된 원인 2개:

1. `confidence_threshold = 0.5` 과도하게 높음
   - 실내 환경에서 MobileNet-SSD v2 COCO 검출 신뢰도가 0.3~0.49 범위에 집중됨
   - 모든 실제 검출이 필터링되어 bbox 발행 없음 → follow_controller 무반응

2. `/vision/person_bbox` QoS 불일치
   - `detector_node`: BEST_EFFORT 발행
   - `panel_server.py`: `depth=10` (rclpy 기본 RELIABLE) 구독
   - ROS 2 규칙상 BEST_EFFORT publisher + RELIABLE subscriber = 연결 비호환, 무음 드롭
   - 검출이 일어나도 패널은 영원히 "person not detected" 표시

적용된 수정 (`d0a0f2c` → `9422dea`):
- `vision.launch.py`: `confidence_threshold` 0.5 → 0.2
- `vision.launch.py`: `publish_debug_image` False → True
- `panel_server.py`: `/vision/person_bbox` 구독 QoS RELIABLE → BEST_EFFORT
- `panel_server.py`: `/vision/debug_image` 구독 추가 (BEST_EFFORT QoS)
- `panel_server.py`: `_debug_image_callback` 추가, `get_camera_frame()` 수정
  - debug_image가 2초 이내 신선하면 우선 반환 → 패널 카메라 화면에 검출 bbox 자동 표시
- `index.html`: camera-toolbar 4열 → 2열 그리드, 반응형 붕괴 규칙 제외
  - 배열: [카메라닫기 | 추종시작] / [새로고침 | 추종끄기]

Pi5 검증:
```bash
cd ~/BuddyBot && git pull origin main
cd software/pi5/ros2_ws && source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select buddybot_vision buddybot_panel
source install/setup.bash && cd ~/BuddyBot
bash scripts/start_presentation_mode.sh mapping
```
- 패널 카메라 화면에 초록 박스 → 검출 성공, 추종 시작 가능
- 박스 없으면 모델 경로 확인: `ros2 run buddybot_vision detector_node --ros-args --log-level info 2>&1 | grep model_`

PRD 참조: PART 3 Cycle 5 실기검증 M3(사람추종), PRD Section 2.2 `/vision/person_bbox` 토픽

## 2026-04-28 Manual Avoidance Toggle + Checkpoint Ack

- New field feedback:
  - manual driving should be able to bypass LiDAR avoidance
  - obstacle avoidance is still needed for autonomous navigation and follow mode
  - pressing checkpoint go sometimes appeared to do nothing
- What changed:
  - `lidar_avoidance_node.py` now accepts `/system/manual_avoidance_enabled`
  - manual driving bypasses LiDAR avoidance when that toggle is `False`
  - autonomous navigation and follow commands still go through LiDAR avoidance as before
  - panel UI now exposes a `수동 회피 ON/OFF` control inside the manual-drive card
  - panel publishes the toggle state with transient-local QoS so restart order is less fragile
  - waypoint manager command subscribers now use reliable + volatile command QoS instead of transient-local
  - panel waits briefly for `waypoint_manager` navigation-status acknowledgement after checkpoint/route requests and raises an API error if the request was published but not acknowledged
- Operational expectation on Pi:
  - default manual mode feels direct because manual avoidance is off
  - if the operator wants extra protection during slow indoor tests, manual avoidance can be turned on from the panel
  - checkpoint go should now either start moving or return a clear panel error instead of silently doing nothing
