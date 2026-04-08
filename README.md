# BuddyBot

`BuddyBot`은 실제 로봇 하드웨어 쪽 저장소입니다.

이 레포는 라즈베리파이 5와 라즈베리파이 Pico에서 돌아가는 실제 로봇 제어 스택을 담고 있습니다.

포함 기능:
- ROS 2 기반 로봇 스택
- Pi5 <-> Pico 시리얼 브리지
- 수동 조작
- 카메라 기반 사용자 추종
- LiDAR 기반 회피구동
- LiDAR / waypoint navigation
- Pi5 로컬 웹 UI
- Pico 펌웨어

## 역할 분리

- 서버컴: `BuddyBot-ai`
- 라즈베리파이 5: `BuddyBot`
- 라즈베리파이 Pico: `firmware/pico_motor_controller`

## 지금 바로 가능한 운용 모드

### 1. 오프라인 Standalone Mode

서버컴 없이 Pi5와 Pico만으로 시연/테스트하는 모드입니다.

가능한 것:
- Pi5 로컬 웹 UI 접속
- 수동 조작
- 추종 상태 전환
- LiDAR 기반 안전 우회
- 체크포인트 저장 / 이동
- 맵 클릭으로 좌표 확인
- 현재 위치 기준 체크포인트 저장

### 2. Assistant Mode

서버컴과 연결해서 쓰는 상위 모드입니다.

가능한 것:
- BuddyBot-ai로 채팅 전달
- AI 비서 기능
- 날씨 / 시간 / 메모리 / 상위 자연어 명령

## 주요 패키지

- `buddybot_base`: Pi5 <-> Pico 시리얼 브리지
- `buddybot_system`: command mux, mode manager, safety supervisor, lidar avoidance
- `buddybot_vision`: 사용자 추종 및 비전 제어
- `buddybot_nav`: waypoint manager, navigation
- `buddybot_voice`: Pi5에서 서버 AI로 연결되는 voice bridge
- `buddybot_panel`: Pi5 로컬 웹 UI

## 하드웨어 기준

- Raspberry Pi 5
- Raspberry Pi Pico
- 3륜 옴니 / Kiwi drive 베이스
- LiDAR
- 카메라
- Pi5 <-> Pico USB 시리얼 연결

## 핀 매핑 기준

- Motor 0: `GP2 / GP0 / GP1 / GP3 / GP14`
- Motor 1: `GP8 / GP6 / GP7 / GP9 / GP15`
- Motor 2: `GP12 / GP10 / GP11 / GP13 / GP16`

상세 문서:
- `docs/pin_mapping.md`

## Pi5 권장 환경

- Ubuntu 24.04
- ROS 2 Jazzy
- `python3-serial`

## Pi5 설치

```bash
git clone https://github.com/rasasoe/BuddyBot.git
cd BuddyBot
bash scripts/setup_pi5.sh
```

위 스크립트가 자동으로 해주는 것:
- apt 의존성 설치
- ROS 패키지 의존성 설치
- 누락된 `resource` / `__init__.py` 점검 및 보정
- `colcon build --symlink-install`

## 제일 쉬운 오프라인 시연 시작

Pi5에서 아래 두 줄이면 시작입니다.

```bash
cd ~/BuddyBot
bash scripts/start_offline_demo.sh
```

Run the full Pi5 stack with preflight checks in one command:

```bash
cd ~/BuddyBot
bash scripts/start_all_pi5.sh
```

Run the full Pi5 stack without the camera pipeline:

```bash
cd ~/BuddyBot
BUDDYBOT_DISABLE_CAMERA=1 bash scripts/start_all_pi5.sh
```

## Real map waypoint workflow

To save waypoints from a real LiDAR map instead of the synthetic waypoint view:

```bash
cd ~/BuddyBot
bash scripts/start_mapping_panel.sh
```

Or start the same flow through the all-in-one launcher:

```bash
cd ~/BuddyBot
bash scripts/start_all_pi5.sh mapping
```

If LiDAR auto-start is unstable, start real-map mode with a detached LiDAR boot first:

```bash
cd ~/BuddyBot
BUDDYBOT_DISABLE_CAMERA=1 BUDDYBOT_DISABLE_PICO=1 bash scripts/start_mapping_real_lidar.sh
```

Notes:
- Your LiDAR driver must already be publishing `/scan`
- When SLAM is healthy, the panel changes from `Map: synthetic` to `Map: ROS OccupancyGrid`
- Click a map cell, type a waypoint name, then use `Save clicked point`
- If `/scan` is missing, start your LiDAR driver first; otherwise SLAM cannot create `/map`

## Pi5 local hotspot mode

Hotspot mode is disabled by default to avoid accidental AP-mode switching during normal development.
You must explicitly opt in with `BUDDYBOT_ALLOW_HOTSPOT=1` before running the hotspot scripts.
The saved hotspot profile is also created with `autoconnect no`, so reboot does not switch `wlan0` back into AP mode.

You do not need Tailscale, VPS, or internet for local control if Pi5 opens its own Wi-Fi AP.

One-time setup:

```bash
cd ~/BuddyBot
BUDDYBOT_ALLOW_HOTSPOT=1 bash scripts/setup_pi5_hotspot.sh
```

Start hotspot:

```bash
cd ~/BuddyBot
BUDDYBOT_ALLOW_HOTSPOT=1 bash scripts/start_pi5_hotspot.sh

Remove an existing hotspot profile and stop reboot-time fallback:

```bash
bash scripts/disable_pi5_hotspot.sh
```
```

Default values:
- SSID: `BuddyBot-Local`
- Password: `BuddyBot1234!`
- Panel URL: `http://192.168.50.1:8090`

## Startup behavior summary

`bash scripts/start_offline_demo.sh`
- Starts the Pi5 local panel backend
- Starts Pico bridge, system mux/safety nodes, camera, detector, follow controller, and waypoint manager
- Tries to auto-start an `sllidar_ros2` driver if that package is installed and a likely serial port exists
- Keeps running in the foreground until you press `Ctrl+C`

`bash scripts/start_all_pi5.sh`
- Resets ROS discovery first
- Probes attached Pi5 devices
- Runs `check_all_devices.sh` as a preflight check
- Starts the offline demo stack in one step

`bash scripts/start_mapping_panel.sh`
- Starts everything from the offline demo
- Adds SLAM toolbox for live map generation
- Tries to auto-start `sllidar_ros2` the same way
- If `/scan` is still missing, the panel stays on `Map: synthetic`

`bash scripts/start_all_pi5.sh mapping`
- Runs the same preflight flow
- Starts the mapping panel stack in one step

## Quick device check

Before a demo, you can verify Pico, LiDAR, camera, and microphone with one command:

```bash
cd ~/BuddyBot
bash scripts/check_all_devices.sh
```

This script:
- Detects Pico, LiDAR, and camera using stable `/dev/serial/by-id` and `/dev/v4l/by-id` paths when available
- Starts each device path one-by-one in a short runtime check
- Reports whether `/buddybot/pico_status`, `/scan`, and `/camera/image_raw` appear
- Shows recent logs for the failing device immediately
- Starts the camera in a conservative USB profile by default: `320x240`, `15fps`, `10Hz` publish
- You can override that profile with `BUDDYBOT_CAMERA_WIDTH`, `BUDDYBOT_CAMERA_HEIGHT`, `BUDDYBOT_CAMERA_FPS`, and `BUDDYBOT_CAMERA_PUBLISH_RATE`

## Manual drive behavior

- Manual drive buttons are latched
- Press `Forward`, `Backward`, `Turn Left`, or `Turn Right` once and the robot keeps moving
- Press `Stop` to clear the command and publish zero velocity
- The panel status shows `Manual drive: latched` while a drive command is active

## Development vs hotspot mode

- For daily development, stay on your normal Wi-Fi or hotspot and use `http://PI5_IP:8090`
- Pi5 hotspot mode is optional and mainly for demos where you want the phone to connect directly to the robot
- When Pi5 switches `wlan0` into hotspot/AP mode, it will usually stop using the previous Wi-Fi connection

접속 주소:
- Pi5 자체 브라우저: `http://127.0.0.1:8090`
- 같은 와이파이 휴대폰: `http://PI5_IP:8090`

## Pico 준비

먼저 Pico에 MicroPython UF2를 설치합니다.

그 다음 `firmware/pico_motor_controller/` 안의 파일들을 Pico 루트에 복사합니다.

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
- Pico 루트에 `main.py`가 있어야 전원 인가 시 자동 실행됩니다.

## 수동으로 실행하고 싶을 때

Pi5에서 아래 순서로 실행하면 됩니다.

### 1. Pico bridge 실행

```bash
ros2 run buddybot_base pico_bridge_node
```

### 2. 시스템 노드 실행

```bash
ros2 run buddybot_system command_mux_node
ros2 run buddybot_system mode_manager_node
ros2 run buddybot_system safety_supervisor_node
ros2 run buddybot_system lidar_avoidance_node
```

### 3. 추종 노드 실행

```bash
ros2 run buddybot_vision follow_controller_node
```

### 4. waypoint manager 실행

```bash
ros2 run buddybot_nav waypoint_manager_node
```

### 5. Pi5 로컬 패널 실행

```bash
ros2 run buddybot_panel panel_server
```

## Pi5 로컬 패널에서 되는 것

- 수동 조작
- 추종 시작 / 중지
- 실시간 맵 토픽이 있으면 OccupancyGrid 기반 미니맵 표시
- 맵이 없으면 체크포인트 기반 합성 미니맵 표시
- 맵 클릭으로 좌표 채우기
- 현재 위치 기준 체크포인트 저장
- 체크포인트 선택 이동
- 로컬 텍스트 명령
- 브라우저 음성 입력
- command mux 상태를 통해 회피/안전 상태 간접 확인

## 회피구동 동작 방식

- 사용자 추종은 카메라 기반 제어를 사용합니다.
- 장애물 회피는 LiDAR `/scan` 기반으로 동작합니다.
- `lidar_avoidance_node`가 전방 장애물을 감지하면 `/cmd_vel_safety_override`를 발행합니다.
- `command_mux_node`는 이 안전 override를 follow/nav/manual보다 높은 우선순위로 반영합니다.
- 가까운 장애물은 정지 또는 후진+회전, 여유가 있는 장애물은 제자리 회전 우회로 처리합니다.

즉:
- 사람 추종: 카메라
- 장애물 회피: LiDAR
- 최종 주행 출력: command mux

## 미니맵 / 체크포인트 동작 방식

### 실시간 맵이 있는 경우

- `/map` 토픽을 읽어 미니맵 표시
- `/amcl_pose` 또는 `/odom` 기준 현재 위치 표시
- 미니맵 클릭으로 좌표 입력
- 현재 위치를 이름만 넣고 바로 체크포인트로 저장 가능

### 실시간 맵이 없는 경우

- `waypoints.yaml` 기준으로 합성 미니맵 생성
- 저장된 체크포인트 좌표를 기준으로 빠른 시연 가능

## 체크포인트 파일

기준 파일:

- `software/pi5/ros2_ws/src/buddybot_nav/config/waypoints.yaml`

이 파일은 아래에서 함께 사용합니다.
- navigation
- waypoint manager
- Pi5 로컬 패널
- 서버측 체크포인트 기능

## Assistant Mode 연결

서버컴이 있을 때만 아래를 추가 실행합니다.

```bash
ros2 run buddybot_voice voice_interface --ros-args -p buddybot_ai_url:=http://SERVER_PC_IP:8000
```

그리고 Pi5 로컬 패널에서 Assistant Mode를 켜면 됩니다.

## 자주 나오는 빌드 에러와 해결

### 1. `can't copy 'resource/buddybot_nav': doesn't exist`

원인:
- `buddybot_nav`는 `ament_python` 패키지이고 `resource/buddybot_nav` 마커 파일이 필요합니다.
- 이 파일이 빠진 예전 커밋을 받은 경우 발생할 수 있습니다.

해결:
```bash
cd ~/BuddyBot
git pull
bash scripts/setup_pi5.sh
```

### 2. `buddybot_voice ... doesn't contain an '__init__.py' file`

원인:
- 예전 커밋의 `buddybot_voice`는 파이썬 패키지 폴더가 빠져 있어서 발생할 수 있습니다.

해결:
```bash
cd ~/BuddyBot
git pull
bash scripts/setup_pi5.sh
```

### 3. 이전 빌드 캐시 때문에 계속 이상한 에러가 날 때

아래처럼 워크스페이스 빌드 산출물만 지우고 다시 빌드합니다.

```bash
cd ~/BuddyBot/software/pi5/ros2_ws
rm -rf build install log
colcon build
source install/setup.bash
```

### 4. 패키지 설치 후에도 ROS가 명령을 못 찾을 때

빌드 후 반드시 아래를 다시 실행합니다.

```bash
cd ~/BuddyBot/software/pi5/ros2_ws
source install/setup.bash
```

그래도 `ros2 run buddybot_panel panel_server` 에서 `No executable found`가 나오면:

```bash
cd ~/BuddyBot
git pull
cd ~/BuddyBot/software/pi5/ros2_ws
rm -rf build install log
cd ~/BuddyBot
bash scripts/setup_pi5.sh
```

### 5. 설치가 자꾸 꼬일 때 전체 점검만 먼저 하고 싶다면

```bash
cd ~/BuddyBot
bash scripts/doctor_pi5.sh
```

자동 수정까지 하고 싶다면:

```bash
cd ~/BuddyBot
bash scripts/doctor_pi5.sh --fix
```

## 팀원 역할 분리

### 서버컴 담당

`BuddyBot-ai` 설치 및 실행

### Pi5 담당

이 `BuddyBot` 설치 및 ROS2 bringup

### Pico 담당

MicroPython 설치 후 `firmware/pico_motor_controller` 업로드

## 오프라인 시연 인계 포인트

팀원에게는 아래처럼 전달하면 됩니다.

1. `BuddyBot`만 받아도 오프라인 모드 시연 가능
2. Pi5에서 `bash scripts/setup_pi5.sh` 한 번 실행
3. `bash scripts/start_offline_demo.sh`로 바로 데모 시작
4. 휴대폰으로 Pi5 패널 접속 가능
5. 수동 조작, 체크포인트 저장/이동, 맵 확인, LiDAR 회피 시연은 서버 없이 가능
6. 서버컴이 붙으면 AI 비서 기능만 추가됨

## 중요한 현실적 주의사항

이 레포는 설치와 소프트웨어 연동, UI 시연을 시작하기에 충분합니다.

하지만 실제 로봇 완성은 아래 하드웨어 검증이 필요합니다.
- 모터 방향 보정
- Kiwi drive 운동학 검증
- 전진 / 후진 / 좌 / 우 / 회전 보정
- 오도메트리 검증
- 추종 튜닝
- 네비게이션 튜닝
- LiDAR 회피 파라미터 튜닝

즉:
- 오프라인 시연 / 기능 테스트는 가능
- 최종 실주행 완성도는 하드웨어 캘리브레이션이 남아 있음

## 같이 보면 좋은 파일

- `README.md`
- `docs/TEAM_SETUP_PI5_AND_PICO.md`
- `docs/pin_mapping.md`
- `docs/bringup.md`

## 폴더 구조

```text
BuddyBot/
  docs/
  firmware/
    pico_motor_controller/
  software/
    pi5/ros2_ws/src/
      buddybot_base/
      buddybot_system/
      buddybot_vision/
      buddybot_nav/
      buddybot_voice/
      buddybot_panel/
      buddybot_msgs/
  README.md
```
