# BuddyBot Pi5 and Pico Setup

## Role split

- `BuddyBot-ai`: server PC
- `BuddyBot`: Raspberry Pi 5
- `firmware/pico_motor_controller`: Raspberry Pi Pico

## Raspberry Pi 5 requirements

- Ubuntu 24.04
- ROS 2 Jazzy
- Python serial package
- USB connection to Pico
- camera and LiDAR connected as needed

## Pi 5 install

Ubuntu 24.04 uses PEP 668 externally-managed Python. Prefer apt packages and `pipx` for command-line tools such as `mpremote`; avoid `python3 -m pip install --user ...` on the Pi system Python.

```bash
git clone https://github.com/rasasoe/BuddyBot.git
cd BuddyBot
sudo apt update
sudo apt install -y pipx python3-venv python3-serial python3-pip psmisc ros-jazzy-nav-msgs ros-jazzy-tf2-ros
python3 -m pipx ensurepath || true
export PATH="$HOME/.local/bin:$PATH"
pipx install mpremote || true
cd software/pi5/ros2_ws
colcon build
source install/setup.bash
```

## Pi 5 run order

가장 권장하는 최신 실행 방식은 개별 노드 수동 실행보다 레포의 런처 스크립트를 사용하는 것입니다.

### Recommended rebuild after pull

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

### Recommended demo launch

일반 모드:

```bash
cd ~/BuddyBot
bash scripts/start_all_pi5.sh mapping
```

USB 전원/카메라 안정성이 나쁠 때 발표용 모드:

```bash
cd ~/BuddyBot
bash scripts/start_presentation_mode.sh mapping
```

프레젠테이션 모드 기본값:
- preflight 재개방 반복 비활성화
- 마이크 상시 리스너 비활성화
- Pi speaker 출력 비활성화
- 카메라 저대역폭 설정 유지
- detector 주기 완화
- 자동 디버그 번들 수집 유지

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

### 3. Follow / vision

```bash
ros2 run buddybot_vision follow_controller_node
```

### 4. Navigation / waypoint manager

```bash
ros2 run buddybot_nav waypoint_manager_node
```

### 5. Voice bridge to server PC

Replace `SERVER_PC_IP` with the real server IP.

```bash
ros2 run buddybot_voice voice_interface --ros-args -p buddybot_ai_url:=http://SERVER_PC_IP:8000
```

### 6. Pi5 local web panel

```bash
ros2 run buddybot_panel panel_server
```

Open from phone or browser:

- `http://PI5_IP:8090`

Standalone mode:

- server PC not required
- local voice command mode works
- manual drive, follow toggle, waypoint go/save work

Assistant mode:

- enable from the Pi5 panel
- set `http://SERVER_PC_IP:8000`
- chat requests are forwarded to `BuddyBot-ai`

## Pico firmware deploy

Install MicroPython UF2 on the Pico first.

Then copy these files from `firmware/pico_motor_controller/` to the Pico root:

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

`main.py` must exist at the Pico root for auto-start.

## Hardware notes

- Pi 5 <-> Pico uses USB serial, usually `/dev/ttyACM0`
- source-of-truth pin mapping is in `docs/pin_mapping.md`
- waypoint data is stored in `software/pi5/ros2_ws/src/buddybot_nav/config/waypoints.yaml`

## Team handoff checklist

1. Start the server PC app first.
2. Confirm `http://SERVER_PC_IP:8000/health` works.
3. Power the robot and connect Pico via USB.
4. Start Pi 5 ROS2 nodes.
5. Open the web GUI from the server PC and test:
   - manual drive
   - follow on/off
   - voice chat
   - waypoint go
6. Optionally run the Pi5 local panel and test from a phone browser.
