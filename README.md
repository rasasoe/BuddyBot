# BuddyBot

`BuddyBot`은 실제 로봇 하드웨어 측 저장소입니다.

이 레포는 라즈베리파이 5와 라즈베리파이 Pico에서 돌아가는 실제 로봇 제어 스택을 담고 있습니다.

포함된 내용:
- ROS 2 스택
- Pi5 <-> Pico 시리얼 브리지
- command mux / mode manager / safety supervisor
- 비전 기반 사용자 추종
- LiDAR 기반 waypoint navigation
- Pi5 로컬 웹 패널
- Pico 펌웨어

## 전체 시스템 역할 분리

- 서버컴: `BuddyBot-ai`
- 라즈베리파이 5: `BuddyBot`
- 라즈베리파이 Pico: `firmware/pico_motor_controller`

## 운영 모드

### 1. Standalone Mode

서버컴 없이 Pi5만으로 동작하는 모드입니다.

가능한 기능:
- Pi5 로컬 웹 UI
- 수동 조작
- 추종 시작 / 중지
- 체크포인트 저장 / 이동
- Pi5 로컬 음성 명령

### 2. Assistant Mode

서버컴과 연결해서 사용하는 모드입니다.

가능한 기능:
- `BuddyBot-ai`로 채팅 요청 전달
- AI 비서 기능
- 더 자연스러운 자연어 처리
- 날씨 / 메모리 / 상위 비서 기능

## 주요 패키지

- `buddybot_base`: Pi5 <-> Pico 시리얼 브리지
- `buddybot_system`: command mux, mode manager, safety supervisor
- `buddybot_vision`: 사용자 추종 및 비전 제어
- `buddybot_nav`: waypoint manager, navigation
- `buddybot_voice`: Pi5에서 서버 AI로 연결되는 voice bridge
- `buddybot_panel`: Pi5 로컬 웹 UI

## 가정하는 하드웨어 구성

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

## Raspberry Pi 5 권장 환경

- Ubuntu 24.04
- ROS 2 Jazzy
- python serial 패키지
- 선택 사항: Assistant Mode용 인터넷/사내망 연결

## Pi5 설치 방법

```bash
git clone https://github.com/rasasoe/BuddyBot.git
cd BuddyBot
sudo apt update
sudo apt install python3-serial
python3 -m pip install fastapi uvicorn requests pyyaml
cd software/pi5/ros2_ws
colcon build
source install/setup.bash
```

## Pi5 실행 순서

### 1. Pico bridge 실행

```bash
ros2 run buddybot_base pico_bridge_node
```

### 2. 시스템 노드 실행

```bash
ros2 run buddybot_system command_mux_node
ros2 run buddybot_system mode_manager_node
ros2 run buddybot_system safety_supervisor_node
```

### 3. 사용자 추종 노드 실행

```bash
ros2 run buddybot_vision follow_controller_node
```

### 4. waypoint manager 실행

```bash
ros2 run buddybot_nav waypoint_manager_node
```

### 5. 선택 사항: 서버컴 연결용 voice bridge 실행

아래의 `SERVER_PC_IP`를 실제 서버 주소로 바꿔 사용합니다.

```bash
ros2 run buddybot_voice voice_interface --ros-args -p buddybot_ai_url:=http://SERVER_PC_IP:8000
```

### 6. Pi5 로컬 웹 패널 실행

```bash
ros2 run buddybot_panel panel_server
```

접속 주소:
- Pi5 로컬: `http://127.0.0.1:8090`
- 같은 네트워크 휴대폰: `http://PI5_IP:8090`

## Pi5 로컬 패널에서 가능한 것

- 수동 조작
- 추종 시작 / 중지
- 체크포인트 저장
- 체크포인트 이동
- 브라우저 로컬 음성 명령
- Assistant Mode 토글

## Pi5 로컬 패널 동작 방식

Assistant Mode가 꺼져 있으면:
- 로컬 명령은 Pi5 내부에서 처리
- 서버컴 없이 사용 가능

Assistant Mode가 켜져 있으면:
- Pi5 패널이 `BuddyBot-ai`로 채팅/명령을 전달
- 서버컴 접속 가능해야 함

즉:
- 평소에는 `Standalone Mode`
- AI 비서가 필요할 때만 `Assistant Mode`

## Pico 펌웨어 올리는 방법

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

## 체크포인트 파일

주요 waypoint 파일:

- `software/pi5/ros2_ws/src/buddybot_nav/config/waypoints.yaml`

이 파일은 아래에서 같이 사용합니다.
- navigation
- waypoint manager
- 서버측 체크포인트 기능
- Pi5 로컬 패널 체크포인트 기능

## 팀원별 설치 기준

### 서버컴 담당

`BuddyBot-ai` 레포를 사용합니다.

### Pi5 담당

이 `BuddyBot` 레포를 사용합니다.

### Pico 담당

MicroPython 설치 후 `firmware/pico_motor_controller`를 업로드합니다.

## 팀원에게 꼭 같이 전달할 검증 주의사항

이 레포는 설치와 구조 파악, 소프트웨어 연동 시작에는 충분합니다.

하지만 실제 로봇 완성에는 아래 하드웨어 검증이 꼭 필요합니다.
- 모터 방향 보정
- Kiwi drive 운동학 검증
- 전진 / 후진 / 좌 / 우 / 회전 보정
- 오도메트리 검증
- 사용자 추종 튜닝
- 네비게이션 튜닝

즉 현재 상태는:
- 설치 가능
- 구조 파악 가능
- UI / 제어 흐름 검증 가능

하지만 여전히 필요한 것:
- 실제 하드웨어 캘리브레이션

## 팀원이 같이 보면 좋은 파일

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
