<p align="right"><a href="README.md">한국어</a> &nbsp; / &nbsp; <strong>English</strong></p>

<p align="center"><img src="docs/assets/portfolio/buddybot-banner.svg" width="100%" alt="BuddyBot — home AI serving robot prototype"></p>

**Home AI Serving Robot Prototype**  
March 2025–June 2026 · Three-person team · **Team lead / system architect / integrator**

<p align="center"><img src="docs/assets/portfolio/buddybot-hero-editorial.jpg" width="100%" alt="Actual BuddyBot robot, showing the complete upper sensor and lower omnidirectional wheels"></p>

The original idea was to **build an AI-assisted robot that could respond to voice requests, understand its surroundings, navigate around obstacles, and follow people indoors**. Rather than presenting an already finished commercial serving robot, this project documents a physical prototype integrating mobility, perception, interaction, and safety control.

[Development progression](#development-progression-mrp3mv4--amr--buddybot) · [Real robot demos](#real-robot-demonstrations) · [System architecture](#system-architecture) · [My contribution](#team-and-contributions)

---

## From idea to requirements

An indoor serving robot needs more than motor movement. We identified a set of capabilities to build and integrate:

- **Mobility:** Three-wheel omnidirectional drive, encoders, waypoint navigation
- **Perception:** LiDAR/ToF sensing and obstacle avoidance; camera-based person detection
- **Interaction:** Microphone, STT voice commands and user-facing controls
- **System safety:** Command arbitration, software stopping, communication watchdog
- **Integration:** ROS 2 perception and planning on Raspberry Pi 5, motor control on Raspberry Pi Pico

**Scope:** The project demonstrates indoor navigation and interaction, **not** end-to-end payload loading, item transport and delivery or consumer-product certification.

## Development progression: MRP3MV4 → AMR → BuddyBot

The final robot was not built from scratch in one step. Three **separate repositories** document how our engineering experience grew from **using an embedded robot control board → implementing motor feedback → integrating robotics and AI into a ROS 2 system**. They are not versions of one continuously evolving codebase.

### 01 / [MRP3MV4 — AVR/LM629 robot experiments](https://github.com/rasasoe/MRP3MV4)

<p align="center"><img src="docs/assets/portfolio/evolution-mrp3mv4.gif" width="460" alt="Actual AVR/LM629-based mobile robot demonstration"></p>

**What we did:** Experimented with the AVR/LM629-based three-wheel holonomic drive and PSD proximity sensing, with camera/sensor demonstration modes. This taught us how sensor input influences robot movement within a board-based control setup.

**What came next:** Move beyond calling existing demo-control routines and implement wheel-speed feedback and kinematics directly.

### 02 / [AMR — Direct Pico encoder and proportional speed control](https://github.com/rasasoe/AMR)

<p align="center"><img src="docs/assets/portfolio/evolution-amr.gif" width="460" alt="Actual AMR wheel-control development and assembly footage"></p>

**What we did:** Implemented encoder RPM feedback and a proportional control loop on Raspberry Pi Pico. Used inverse kinematics to translate desired robot movement and rotation into per-wheel target speeds.

**What came next:** A reliable drivetrain alone is not an autonomous indoor robot. It needed navigation, obstacle perception, person following and voice interaction.

### 03 / BuddyBot — Integrated ROS 2 indoor mobile robot

**What we did:** Added Raspberry Pi 5 for LiDAR, vision, ROS 2 navigation and voice interaction, with Raspberry Pi Pico handling low-level motors and watchdog behavior. A command mux arbitrates among navigation, following, manual control and stopping.

**Outcome:** Demonstrated checkpoint navigation, obstacle avoidance, following, voice commands and emergency stopping on the physical robot. See the motion footage below.

## Real robot demonstrations

### Navigation and LiDAR obstacle avoidance

<p align="center"><img src="docs/assets/portfolio/checkpoint-navigation-polished.gif" width="560" alt="Animated demonstration of BuddyBot waypoint navigation and LiDAR obstacle avoidance"></p>

[Color-corrected GIF](docs/assets/portfolio/checkpoint-navigation-polished.gif) · [Original GIF](docs/assets/portfolio/checkpoint-navigation.gif)

### Person detection and physical following

<p align="center"><img src="docs/assets/portfolio/person-follow-panel.gif" width="480" alt="Real-time camera detection and following control display"></p>

<p align="center"><a href="docs/assets/portfolio/person-follow-physical.mp4"><img src="docs/assets/portfolio/person-follow-physical-cover.jpg" width="480" alt="Play the real person-following robot demonstration"></a></p>

[Watch real following video](docs/assets/portfolio/person-follow-physical.mp4)

### Voice-controlled movement

<p align="center"><a href="docs/assets/portfolio/voice-command.mp4"><img src="docs/assets/portfolio/voice-command-cover.jpg" width="480" alt="Play the voice-command robot motion demo"></a></p>

[Watch original video with audio](docs/assets/portfolio/voice-command.mp4)

### Server AI question and voice response

<p align="center"><a href="docs/assets/portfolio/weather-assistant.mp4"><img src="docs/assets/portfolio/weather-assistant-cover.jpg" width="580" alt="Play the server AI voice response demonstration"></a></p>

[Watch server interaction video](docs/assets/portfolio/weather-assistant.mp4) — Optional [BuddyBot-ai](https://github.com/rasasoe/BuddyBot-ai) provides STT/TTS, dialogue and high-level action requests.

## System architecture

<picture>
  <source media="(max-width: 600px)" srcset="docs/assets/portfolio/architecture-mobile.svg">
  <img src="docs/assets/portfolio/architecture-desktop.svg" width="100%" alt="Sensors and user requests flow through ROS 2 Raspberry Pi 5 arbitration and safety to Raspberry Pi Pico motor control">
</picture>

**Raspberry Pi 5 / Brain:** ROS 2 Jazzy sensor processing, navigation, following, manual commands, safety priority and robot status.

**Raspberry Pi Pico / Motor & Safety:** Encoder feedback, kinematics, PWM, heartbeat and watchdog. Pi 5 and Pico use a USB CDC text protocol.

**Optional BuddyBot-ai server:** Speech services, user dashboard and high-level robot requests, without direct motor PWM access.

### Engineering decisions

1. **One final command source:** `command_mux` prioritizes `E-STOP > Safety Override > Manual > Navigation > Follow > Idle`.
2. **Separate Linux processes from low-level motor safety:** Pico watchdog stops the drive when communication is lost.
3. **Traceable control protocol:** Line-based `HB`, `CMD`, `ACK`, `STAT`, `SAFE` messages help diagnose hardware integration issues.

### Actual integrated user interface

<p align="center"><img src="docs/assets/portfolio/system-dashboard.png" width="100%" alt="BuddyBot operational dashboard showing LiDAR, camera, following and controls"></p>

## Team and contributions

**Three-person team · Team lead, system architecture and integration**

- Designed separation between Raspberry Pi 5 and Pico, and integrated the ROS 2 control path
- Integrated sensing, motor feedback, navigation, following and voice-command subsystems
- Coordinated hardware bring-up, command arbitration, failure investigation and final demonstrations

Subsystem development was shared with teammates. The team result is not represented as entirely individual authorship.

## Results and boundaries

The actual robot demonstration records show navigation, obstacle avoidance, following, voice/manual control, dashboard and software emergency stop.

**Not yet established:** End-to-end serving of physical objects, a standalone physical emergency-stop circuit, quantified repeat-test navigation success/stop latency, hardware-in-the-loop regression testing, and stronger web control access restrictions.

A successful demo is evidence of functionality, not proof of production-grade safety.

## Code and documentation

```text
BuddyBot/
├── firmware/pico_motor_controller/
├── software/pi5/ros2_ws/src/
│   ├── buddybot_base/
│   ├── buddybot_system/
│   ├── buddybot_nav/
│   ├── buddybot_vision/
│   ├── buddybot_voice/
│   └── buddybot_panel/
├── scripts/
└── docs/
```

[Architecture](docs/architecture.md) · [Pi 5/Pico setup](docs/TEAM_SETUP_PI5_AND_PICO.md) · [Bring-up](docs/bringup.md) · [USB protocol](docs/uart_protocol.md) · [Voice commands](docs/voice_commands.md)

The robot requires ROS 2 Jazzy, the actual motor/sensor hardware and per-device configuration. Optional speech and UI server: [BuddyBot-ai](https://github.com/rasasoe/BuddyBot-ai).
