# BuddyBot AI Handoff

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

- User-facing symptom:
  - `forward` still looked like counter-clockwise spin on hardware.
  - `stop` sometimes felt flaky from the browser panel.
- Current conclusion:
  - This was no longer mainly a `pico_bridge`/REPL issue once `pico_status` recovered.
  - The stronger remaining problem was the wheel-mix model on the Pico side.
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
  - Treat the above Pico baseline as the current reference configuration.
  - If motion regresses, first verify `pins.py`, `motor_driver.py`, `encoder.py`, `kinematics.py`, and `config.py` still match this baseline before changing geometry again.
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
