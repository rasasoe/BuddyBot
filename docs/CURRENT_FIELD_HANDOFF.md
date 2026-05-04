# BuddyBot Current Field Handoff

Last updated: 2026-05-04
Repo baseline: local work after `14bccd5` (`Add manual avoidance toggle and checkpoint ack`)

This is the fast resume page for a new laptop, a new Codex session, or the Pi5 field machine. Read this first, then use `AI_HANDOFF.md`, `docs/field_log.md`, and `docs/CODEX_RESUME_WORKFLOW.md` for deeper history.

## Current Working Baseline

- Manual driving is the best known hardware baseline so far. The user reported the robot moves very well after the Pico smoothing and manual-drive tuning work.
- Keep the current Pico motor mapping, wheel geometry, ramp limiting, and manual trim as the locked baseline unless a new single-wheel test proves otherwise.
- The panel manual pad is camera-first: front camera, manual arrows, then quick commands.
- Manual rotation speed was raised after field feedback, and right-turn commands receive a small boost to better match left-turn feel.
- The minimap start button now means live LiDAR accumulation only. It should not make the robot wander automatically.
- Checkpoint motion does not require minimap start. It does require a live pose from `/odom` or `/amcl_pose`.

## Latest Field Change

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

1. Pull `main` on the Pi and start presentation mode.
2. Confirm the manual-control card shows `수동 회피 OFF`.
3. Drive manually with manual avoidance OFF and confirm direct control feel.
4. Toggle manual avoidance ON and confirm it changes panel state.
5. Run:

```bash
curl -s http://127.0.0.1:8090/api/status | python3 -m json.tool
ros2 topic echo --once /buddybot/pico_status
ros2 topic echo --once /odom
```

6. If `/buddybot/pico_status` exists but `/odom` does not, check `encoder_odom.log` and confirm `buddybot_base` was rebuilt.

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
