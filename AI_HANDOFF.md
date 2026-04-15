# BuddyBot AI Handoff

## Current State

BuddyBot is now closer to the offline-first product target.

Working in code:
- Manual drive via `/cmd_vel_manual`
- Follow on/off routing via `/follow/enabled`
- Waypoint save, delete, clear, and go
- Route dispatch support via `/nav/route_goal` compatibility and panel `/api/routes/run`
- Local panel status, map, minimap, camera, and chat APIs
- USB speaker output through `espeak-ng` path in `buddybot_voice`
- New automated verification script: `scripts/verify_system.sh`

Still needs hardware verification:
- Rotation strength and sign on real base
- Follow behavior under real camera detection and bbox timeout
- Route sequence execution on the robot
- E-STOP behavior end-to-end
- USB speaker audio output on the Pi
- Mobile UX thumb reach and operator flow on actual phone

## Build After Pull

```bash
cd ~/BuddyBot/software/pi5/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select \
  buddybot_nav buddybot_panel buddybot_voice
source install/setup.bash
```

## Immediate Verification

```bash
cd ~/BuddyBot
bash scripts/verify_system.sh
```

Then open:

```text
http://<pi-ip>:8090
```

## Known Hardware Items

- Rotation `wz`: verify whether `ROTATION_MIX_GAIN = 1.5` is strong enough on real hardware
- USB speaker: verify `espeak-ng` actually plays through Pi USB audio
- Camera USB stability: keep Logitech C920 on a Pi 5 direct port, not the hub, if possible

## Feature Status

| Feature | Code | Hardware Verified |
|---------|------|-------------------|
| Manual drive (fwd/back/strafe) | ✅ | ✅ |
| Rotation (wz) | ✅ patched/tunable | ❓ needs test |
| Follow mode | ✅ | ❓ needs test |
| Checkpoint save/go | ✅ | ✅ |
| Checkpoint delete | ✅ | ❓ |
| Route sequence | ✅ patched | ❓ |
| USB TTS (espeak) | ✅ | ❓ |
| E-STOP button/API | ✅ | ❓ |
| Mobile panel flow | ✅ partially | ❓ |
| `verify_system.sh` | ✅ new | ❓ |

## Next AI Instructions

Priority 1:
- Run `bash scripts/verify_system.sh` on Pi and fix any FAIL items

Priority 2:
- Test rotation

```bash
ros2 topic pub --once /cmd_vel_manual geometry_msgs/msg/Twist "{angular: {z: 0.5}}"
```

Priority 3:
- Test TTS

```bash
ros2 topic pub --once /voice/response std_msgs/msg/String "{data: '버디봇 준비 완료'}"
```

Priority 4:
- Test route execution from panel
  - save 2 checkpoints
  - add them to a route
  - run route

## File Change Log

- `software/pi5/ros2_ws/src/buddybot_nav/buddybot_nav/waypoint_manager_node.py`
- `software/pi5/ros2_ws/src/buddybot_panel/buddybot_panel/panel_server.py`
- `software/pi5/ros2_ws/src/buddybot_voice/buddybot_voice/voice_interface.py`
- `scripts/setup_pi5.sh`
- `software/pi5/ros2_ws/src/buddybot_nav/config/waypoints.yaml`
- `firmware/pico_motor_controller/config.py`
- `firmware/pico_motor_controller/kinematics.py`
- `firmware/pico_motor_controller/test_kinematics.py`
- `scripts/verify_system.sh`
- `AI_HANDOFF.md`

## Notes

- The panel already had richer functionality than the original PRD draft in several areas.
- Route support existed under destination semantics; this patch set adds `route_goal` compatibility so tools and docs can target one shape.
- Week 7 LiDAR work is effectively present in code.
- Week 8 full camera-LiDAR fusion is still not fully complete as a dedicated shared representation node. Health/status integration exists, but full fusion still needs a real implementation if the checklist must be marked 100% complete.
