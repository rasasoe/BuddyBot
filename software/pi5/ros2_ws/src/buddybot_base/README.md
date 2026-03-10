# BuddyBot Base Package

This package provides the core communication bridge between the Raspberry Pi 5 ROS 2 system and the Raspberry Pi Pico motor controller.

## Architecture

The package consists of three main components:

### 1. pico_bridge_node.py
**Main ROS 2 Node** - The central communication bridge that:
- Subscribes to `/cmd_vel_final` for velocity commands
- Publishes Pico status to `/buddybot/pico_status`
- Publishes safety events to `/buddybot/pico_safety_event`
- Publishes motor RPM data to `/buddybot/pico_rpm`
- Sends heartbeat messages to maintain Pico watchdog
- Handles automatic serial reconnection with exponential backoff

### 2. protocol.py
**UART Protocol Handler** - Manages the text-based UART communication protocol:
- Parses incoming commands from Pi 5
- Formats outgoing responses to Pi 5
- Validates message formats and parameters
- Provides human-readable error handling

### 3. serial_manager.py
**Serial Communication Manager** - Handles low-level serial operations:
- Establishes and maintains serial connection
- Automatic reconnection with exponential backoff
- Thread-safe message sending/receiving
- Connection health monitoring

## Safety Features

- **Velocity Clamping**: All commands are clamped to safe ranges (-1.0 to 1.0)
- **Heartbeat Monitoring**: Regular heartbeat prevents Pico watchdog timeout
- **Automatic Reconnection**: Serial connection loss triggers immediate reconnection attempts
- **Malformed Message Handling**: Invalid messages are logged but don't crash the system
- **Status Timeout Detection**: Missing status updates are detected and reported

## ROS 2 Interfaces

### Subscribers
- `/cmd_vel_final` (geometry_msgs/Twist): Final velocity commands from command multiplexer

### Publishers
- `/buddybot/pico_status` (buddybot_msgs/Status): Pico status including emergency stop state and mode
- `/buddybot/pico_safety_event` (std_msgs/String): Safety events from Pico
- `/buddybot/pico_rpm` (std_msgs/Float32MultiArray): Motor RPM data [m1, m2, m3]

## Parameters

- `serial_port` (string, default: '/dev/ttyAMA0'): Serial device path
- `serial_baudrate` (int, default: 115200): Serial communication baud rate
- `heartbeat_interval` (float, default: 1.0): Heartbeat message interval in seconds
- `status_timeout` (float, default: 5.0): Status message timeout in seconds
- `max_reconnect_attempts` (int, default: 10): Maximum serial reconnection attempts
- `cmd_vel_timeout` (float, default: 0.5): Command velocity timeout in seconds

## Usage

```bash
# Launch the bridge node
ros2 run buddybot_base pico_bridge_node

# With custom parameters
ros2 run buddybot_base pico_bridge_node --ros-args -p serial_port:=/dev/ttyUSB0
```

## Dependencies

- `rclpy`: ROS 2 Python client library
- `buddybot_msgs`: Custom BuddyBot message definitions
- `geometry_msgs`: Standard ROS geometry messages
- `std_msgs`: Standard ROS message types
- `pyserial`: Python serial communication library

## UART Protocol

The node communicates with the Pico using a text-based protocol defined in `docs/uart_protocol.md`. Messages are line-delimited with key=value parameters for easy debugging and monitoring.