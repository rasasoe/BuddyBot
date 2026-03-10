# BuddyBot

라즈베리 파이 5 + 라즈베리 파이 피코 기반 옴니휠 홈 어시스턴트 로봇.

## 프로젝트 구조

```
BuddyBot/
├── firmware/
│   └── pico_motor_controller/    # 피코 마이크로파이썬 펌웨어
├── software/
│   └── pi5/
│       └── ros2_ws/              # ROS 2 Jazzy 워크스페이스
│           └── src/
│               ├── buddybot_msgs/       # 사용자 정의 메시지
│               ├── buddybot_base/       # 핵심 기능
│               ├── buddybot_vision/     # 컴퓨터 비전
│               ├── buddybot_nav/        # 네비게이션 스택
│               ├── buddybot_voice/      # 음성 인터페이스
│               ├── buddybot_system/     # 모니터링/진단
│               └── buddybot_bringup/    # 런치 구성
├── docs/                        # 문서
└── tools/                       # 개발 도구
```

## 주요 기능

- LiDAR 기반 SLAM 네비게이션
- 카메라 기반 사람 추적
- 광학 플로우 비상 정지
- 로컬 음성 인터페이스
- 안전 워치독 아키텍처

## 안전 원칙

1. 피코가 Pi 5 실패 시 로봇 정지 (워치독)
2. 명령어가 중앙 뮤텍스를 우회하지 않음
3. 비상 정지가 최우선
4. 비전이 독립적인 충돌 회피 제공

## 설정

1. Ubuntu 24.04에 ROS 2 Jazzy 설치
2. `./tools/setup.sh` 실행
3. 워크스페이스 빌드: `cd software/pi5/ros2_ws && colcon build`
4. 피코에 펌웨어 플래시
5. 런치: `ros2 launch buddybot_bringup buddybot.launch.py`

고급 안전 기능을 갖춘 라즈베리 파이 5 + 라즈베리 파이 피코 기반 옴니휠 홈 어시스턴트 로봇.

## Architecture

- **Raspberry Pi 5 (Brain)**: ROS 2 Jazzy, vision, navigation, voice, mode manager, command mux
- **Raspberry Pi Pico (Spinal Cord)**: MicroPython, motor control, encoders, PID, watchdog, safety stop

## Key Features

- LiDAR-based SLAM and waypoint navigation
- Camera-based person detection and following
- Optical-flow-based time-to-collision emergency stop
- Local voice interface with wake word
- Strong fail-safe and watchdog-oriented CPS architecture

## Safety Principles

1. Safety first - Pico can stop robot even if Pi 5 fails
2. High-level commands never bypass the command mux
3. Pico implements watchdog timeout and emergency stop latch
4. Modular, readable code suitable for capstone project

## Project Structure

```
BuddyBot/
├── ros2_ws/              # ROS 2 workspace
│   └── src/
│       ├── buddybot_msgs/    # Custom messages
│       ├── buddybot_core/    # Mode manager, command mux, Pico comm
│       ├── buddybot_navigation/  # SLAM, waypoint navigation
│       ├── buddybot_vision/  # Person detection, following, TTC
│       └── buddybot_voice/   # Voice interface
├── pico/                 # Pico MicroPython code
├── docs/                 # Documentation
└── scripts/              # Setup scripts
```

## Setup

1. Install ROS 2 Jazzy on Ubuntu 24.04
2. Clone and build the workspace:
   ```bash
   cd ros2_ws
   colcon build
   ```
3. Flash main.py to Raspberry Pi Pico
4. Connect hardware (LiDAR, camera, motors, etc.)

## Running

```bash
# Source workspace
source ros2_ws/install/setup.bash

# Launch navigation
ros2 launch buddybot_navigation navigation.launch.py

# Launch vision
ros2 run buddybot_vision person_detector &
ros2 run buddybot_vision person_follower &
ros2 run buddybot_vision optical_flow_ttc &

# Launch voice
ros2 run buddybot_voice voice_interface &

# Launch core
ros2 run buddybot_core mode_manager &
ros2 run buddybot_core command_mux &
ros2 run buddybot_core pico_comm &
```