# BuddyBot

BuddyBot은 Raspberry Pi 5와 Raspberry Pi Pico를 사용하는 실제 로봇 제어 저장소입니다.

이 저장소는 다음 역할을 담당합니다.
- ROS 2 기반 로봇 노드
- Pi 5 ↔ Pico USB serial bridge
- command mux / mode manager / safety supervisor
- 비전 기반 사용자 추종
- LiDAR 기반 waypoint navigation
- Pico 모터 제어 펌웨어

## 역할 분리

- 서버컴 GUI 및 AI: `BuddyBot-ai`
- Raspberry Pi 5 실기 제어: `BuddyBot`
- Raspberry Pi Pico 펌웨어: `firmware/pico_motor_controller`

## 핵심 구조

### Raspberry Pi 5

- ROS 2 Jazzy
- 카메라 / LiDAR / 상위 제어
- Pico와 USB serial 통신
- follow, navigation, waypoint manager 실행

### Raspberry Pi Pico

- 모터 PWM 제어
- 엔코더 읽기
- watchdog / brake / safety 처리

## 주요 패키지

- `buddybot_base`: Pi5-Pico bridge
- `buddybot_system`: command mux, mode, safety
- `buddybot_vision`: 사람 추종 제어
- `buddybot_nav`: waypoint manager, navigation
- `buddybot_voice`: 서버컴 AI와 연결하는 voice bridge

## 하드웨어 전제

- Raspberry Pi 5
- Raspberry Pi Pico
- 3륜 omni / kiwi drive 베이스
- LiDAR
- 카메라
- USB로 Pi5 ↔ Pico 연결

## 핀 매핑

실제 배선 기준 소스 오브 트루스:

- Motor 0: `GP2 / GP0 / GP1 / GP3 / GP14`
- Motor 1: `GP8 / GP6 / GP7 / GP9 / GP15`
- Motor 2: `GP12 / GP10 / GP11 / GP13 / GP16`

자세한 내용:

- `docs/pin_mapping.md`

## Raspberry Pi 5 설치

```bash
git clone https://github.com/rasasoe/BuddyBot.git
cd BuddyBot
sudo apt update
sudo apt install python3-serial
cd software/pi5/ros2_ws
colcon build
source install/setup.bash
```

## Raspberry Pi 5 실행 순서

### 1. Pico bridge

```bash
ros2 run buddybot_base pico_bridge_node
```

### 2. System nodes

```bash
ros2 run buddybot_system command_mux_node
ros2 run buddybot_system mode_manager_node
ros2 run buddybot_system safety_supervisor_node
```

### 3. Vision / follow

```bash
ros2 run buddybot_vision follow_controller_node
```

### 4. Navigation

```bash
ros2 run buddybot_nav waypoint_manager_node
```

### 5. Voice bridge

서버컴 IP를 바꿔서 실행:

```bash
ros2 run buddybot_voice voice_interface --ros-args -p buddybot_ai_url:=http://SERVER_PC_IP:8000
```

## Pico 설치

먼저 Pico에 MicroPython UF2를 올립니다.

그 다음 `firmware/pico_motor_controller` 안의 파일을 Pico 루트에 복사합니다.

필수 파일:

- `main.py`
- `config.py`
- `pins.py`
- `motor_driver.py`
- `encoder.py`
- `kinematics.py`
- `pid.py`
- `watchdog.py`
- `safety.py`
- `state.py`
- `uart_protocol.py`

중요:

- Pico 루트에 `main.py`가 있어야 자동 실행됩니다.

## 체크포인트 파일

Waypoint 데이터는 아래 파일에 저장됩니다.

- `software/pi5/ros2_ws/src/buddybot_nav/config/waypoints.yaml`

서버컴 GUI에서 체크포인트를 저장하면 이 파일이 기준 데이터가 됩니다.

## 팀원 설치 안내

Pi 5와 Pico 담당 팀원은 아래 문서를 먼저 보면 됩니다.

- `docs/TEAM_SETUP_PI5_AND_PICO.md`

## 프로젝트 구조

```text
BuddyBot/
├── docs/
├── firmware/
│   └── pico_motor_controller/
├── software/
│   └── pi5/ros2_ws/src/
│       ├── buddybot_base/
│       ├── buddybot_system/
│       ├── buddybot_vision/
│       ├── buddybot_nav/
│       ├── buddybot_voice/
│       └── buddybot_msgs/
└── README.md
```

## 현재 상태

현재 구조상 시스템 아키텍처와 통신 계층은 정리되어 있습니다.
다만 실기 기준으로는 모터 방향 보정, 실제 odometry 계산, kiwi drive 운동학 검증이 계속 중요합니다.
실주행 전에는 반드시 전진/후진/좌우/회전 캘리브레이션 테스트를 수행하세요.

