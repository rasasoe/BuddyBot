# BuddyBot

BuddyBot is the real robot-side repository for Raspberry Pi 5 and Raspberry Pi Pico.

This repository contains:
- the ROS 2 stack for the robot
- Pi 5 to Pico serial bridge
- command mux, mode manager, and safety supervisor
- vision-based follow control
- LiDAR waypoint navigation
- Pi 5 local web panel
- Pico firmware files

## System split

- Server PC: `BuddyBot-ai`
- Raspberry Pi 5: `BuddyBot`
- Raspberry Pi Pico: `firmware/pico_motor_controller`

## Main operating modes

### 1. Standalone mode

No server PC required.

Available:
- Pi 5 local web UI
- manual control
- follow toggle
- waypoint save and waypoint go
- local voice command mode on the Pi 5 panel

### 2. Assistant mode

Server PC required.

Available:
- forward chat requests to `BuddyBot-ai`
- AI assistant features
- richer natural language handling
- weather, memory, and high-level assistant flows

## Main packages

- `buddybot_base`: Pi 5 to Pico serial bridge
- `buddybot_system`: command mux, mode manager, safety supervisor
- `buddybot_vision`: follow and vision control
- `buddybot_nav`: waypoint manager and navigation
- `buddybot_voice`: bridge from Pi 5 to server AI
- `buddybot_panel`: Pi 5 local web UI

## Hardware assumptions

- Raspberry Pi 5
- Raspberry Pi Pico
- 3-wheel omni or kiwi drive base
- LiDAR
- camera
- USB serial between Pi 5 and Pico

## Source-of-truth pin mapping

- Motor 0: `GP2 / GP0 / GP1 / GP3 / GP14`
- Motor 1: `GP8 / GP6 / GP7 / GP9 / GP15`
- Motor 2: `GP12 / GP10 / GP11 / GP13 / GP16`

See:

- `docs/pin_mapping.md`

## Raspberry Pi 5 requirements

- Ubuntu 24.04
- ROS 2 Jazzy
- Python serial package
- optional internet access for assistant mode

## Pi 5 install

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

## Pi 5 run order

### 1. Start Pico bridge

```bash
ros2 run buddybot_base pico_bridge_node
```

### 2. Start system nodes

```bash
ros2 run buddybot_system command_mux_node
ros2 run buddybot_system mode_manager_node
ros2 run buddybot_system safety_supervisor_node
```

### 3. Start follow controller

```bash
ros2 run buddybot_vision follow_controller_node
```

### 4. Start waypoint manager

```bash
ros2 run buddybot_nav waypoint_manager_node
```

### 5. Optional: start voice bridge to server PC

Replace `SERVER_PC_IP` with the real server address:

```bash
ros2 run buddybot_voice voice_interface --ros-args -p buddybot_ai_url:=http://SERVER_PC_IP:8000
```

### 6. Start Pi 5 local web panel

```bash
ros2 run buddybot_panel panel_server
```

Open from a phone or browser:

- Pi 5 local: `http://127.0.0.1:8090`
- phone on same network: `http://PI5_IP:8090`

## What the Pi 5 local panel can do

- manual drive
- follow start and stop
- checkpoint save
- checkpoint go
- local browser voice command
- assistant mode toggle

## Pi 5 local panel behavior

If assistant mode is off:
- local commands stay on the Pi 5
- server PC is not required

If assistant mode is on:
- the Pi 5 panel forwards chat requests to `BuddyBot-ai`
- server PC must be reachable

## Pico firmware deploy

Install MicroPython UF2 on the Pico first.

Then copy the files from `firmware/pico_motor_controller/` to the Pico root.

Required files:

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

Important:

- `main.py` must exist at the Pico root for auto-start

## Waypoint data

The main waypoint file is:

- `software/pi5/ros2_ws/src/buddybot_nav/config/waypoints.yaml`

This file is used by:
- navigation
- waypoint manager
- server-side checkpoint features
- Pi 5 local panel checkpoint features

## Team install summary

### Server PC teammate

Use `BuddyBot-ai`.

### Pi 5 teammate

Use this repository.

### Pico teammate

Flash MicroPython, then upload `firmware/pico_motor_controller`.

## Important validation note

The repository is installable and structured well enough for the team to start immediately.

However, real robot validation still depends on hardware testing:
- motor direction correction
- kiwi drive kinematics verification
- forward, backward, left, right, rotate calibration
- odometry verification
- follow tuning
- navigation tuning

So this repo is ready for:
- setup
- software integration
- UI and control flow testing

But it still needs:
- final hardware calibration on the real robot

## Files that teammates should read

- `README.md`
- `docs/TEAM_SETUP_PI5_AND_PICO.md`
- `docs/pin_mapping.md`
- `docs/bringup.md`

## Project layout

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
│       ├── buddybot_panel/
│       └── buddybot_msgs/
└── README.md
```

