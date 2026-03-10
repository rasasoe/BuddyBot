# BuddyBot

A safe, autonomous home assistant robot featuring Brain vs Spinal Cord architecture, built with Raspberry Pi 5 and Raspberry Pi Pico for reliable human-robot interaction.

## Overview

BuddyBot is a capstone project demonstrating advanced robotics engineering principles through a modular, safety-first autonomous robot. The system implements a "Brain vs Spinal Cord" architecture that separates high-level cognitive functions (Pi 5) from low-level safety-critical motor control (Pico), ensuring fail-safe operation even during system failures. Using ROS 2 Jazzy on Ubuntu 24.04, BuddyBot integrates LiDAR-based navigation, computer vision, and local AI processing for natural human-robot interaction.

## Key Features

- **Autonomous Navigation**: LiDAR-based SLAM with semantic waypoint management
- **Person Following**: Real-time computer vision tracking with smooth pursuit algorithms
- **Multi-Modal Safety**: Hardware, firmware, and software safety layers with emergency stop
- **Command Arbitration**: Priority-based multiplexing prevents conflicting movement commands
- **Omnidirectional Movement**: 3-wheel holonomic drive for smooth, precise navigation
- **Local AI Processing**: On-device computer vision and decision making
- **Voice Integration**: Natural language command processing (planned)

## System Architecture

### Brain vs Spinal Cord Design

BuddyBot implements a distributed architecture separating cognition from control:

```
┌─────────────────┐    UART     ┌─────────────────┐
│   Raspberry Pi 5 │◄──────────►│  Raspberry Pico │
│     (The Brain)  │            │ (The Spinal Cord)│
│                  │            │                  │
│ • ROS 2          │            │ • Motor Control  │
│ • Computer Vision│            │ • Safety Systems │
│ • Navigation     │            │ • Watchdog       │
│ • AI Processing  │            │ • E-Stop         │
└─────────────────┘            └─────────────────┘
         │                              │
         ├─ LiDAR (Navigation)         ├─ Motors
         └─ Camera (Vision)            └─ Encoders
```

### Command Priority Hierarchy

1. **E-STOP** (Hardware/Firmware): Physical emergency stop, watchdog timeout
2. **Manual** (Human): Direct joystick/keyboard control
3. **Safety** (Autonomous): Collision avoidance, obstacle detection
4. **Navigation** (Autonomous): Waypoint following, path planning
5. **Follow** (Autonomous): Person tracking
6. **Idle** (Default): Stationary safe state

## Repository Structure

```
BuddyBot/
├── firmware/           # Pico microcontroller code
│   └── pico_motor_controller/
├── software/           # ROS 2 workspace
│   └── pi5/
│       └── ros2_ws/
│           └── src/    # ROS 2 packages
│               ├── buddybot_base/      # Pi 5 ↔ Pico communication
│               ├── buddybot_vision/    # Computer vision pipeline
│               ├── buddybot_nav/       # Navigation and mapping
│               ├── buddybot_system/    # Command arbitration & safety
│               ├── buddybot_voice/     # Voice interface (planned)
│               └── buddybot_bringup/   # System launch configuration
├── docs/              # Documentation
├── tools/             # Development utilities
└── README.md          # This file
```

## Hardware Stack

### Core Components
- **Raspberry Pi 5**: Main computer running ROS 2 and AI processing
- **Raspberry Pi Pico**: Real-time motor control and safety systems
- **LiDAR Sensor**: 2D laser scanner for navigation and mapping
- **Camera**: RGB camera for computer vision and person tracking
- **Omniwheel Drive**: 3-wheel holonomic base for smooth movement

### Peripheral Interfaces
- **UART**: Deterministic communication between Pi 5 and Pico
- **USB**: Camera and sensor connections
- **GPIO**: Motor drivers and safety interlocks
- **Power Management**: Battery monitoring and distribution

## Software Stack

### ROS 2 Jazzy (Ubuntu 24.04)
- **Middleware**: ROS 2 for inter-process communication
- **Navigation**: Nav2 stack with SLAM and path planning
- **Vision**: OpenCV with custom computer vision pipelines
- **Safety**: Multi-layer safety monitoring and control

### Python Packages
- **buddybot_base**: UART communication bridge
- **buddybot_vision**: Person detection and following
- **buddybot_nav**: Waypoint navigation and mapping
- **buddybot_system**: Command multiplexing and safety supervision

### Pico Firmware
- **Motor Control**: PID-based omnidirectional control
- **Safety Systems**: Watchdog timer and emergency stop
- **Communication**: UART protocol implementation

## Development Status

### Completed ✅
- Brain vs Spinal Cord architecture implementation
- UART communication protocol between Pi 5 and Pico
- Basic motor control with PID algorithms
- Computer vision person detection (MobileNet-SSD)
- Command arbitration system with priority multiplexing
- Navigation waypoint management
- System mode management (IDLE/MANUAL/FOLLOW/NAVIGATION)
- Multi-layer safety systems

### In Progress 🚧
- Full Nav2 navigation stack integration
- Voice command processing
- Multi-sensor fusion (LiDAR + Camera)
- Advanced safety system testing

### Planned 📋
- Cloud integration for remote monitoring
- Multi-robot coordination capabilities
- Learning systems for behavior adaptation
- Commercial deployment preparation

## Quick Start

### Prerequisites
- Ubuntu 24.04 LTS
- ROS 2 Jazzy Jalisco
- Raspberry Pi 5 and Pico hardware
- LiDAR and camera sensors

### Pi 5 Setup (ROS 2)
```bash
# Clone repository
git clone https://github.com/rasasoe/BuddyBot.git
cd BuddyBot

# Run setup script
./tools/setup.sh

# Build ROS 2 packages
cd software/pi5/ros2_ws
colcon build

# Source workspace
source install/setup.bash

# Test basic functionality
ros2 run buddybot_base pico_bridge_node
```

### Pico Setup (Firmware)
```bash
# Navigate to firmware directory
cd BuddyBot/firmware/pico_motor_controller

# Build and flash firmware (using appropriate Pico toolchain)
# Implementation depends on your Pico development setup
```

### Basic System Test
```bash
# Launch vision system
ros2 launch buddybot_vision vision.launch.py

# Launch navigation
ros2 launch buddybot_nav nav.launch.py

# Launch system control
ros2 launch buddybot_system system.launch.py
```

## Roadmap

### Phase 1: Foundation (Completed)
- [x] Brain vs Spinal Cord architecture
- [x] UART communication protocol
- [x] Basic motor control and safety
- [x] Computer vision integration

### Phase 2: Autonomous Behaviors (In Progress)
- [x] Person following
- [x] Waypoint navigation
- [ ] Full Nav2 integration
- [ ] Voice commands

### Phase 3: System Integration (Q2 2026)
- [ ] Multi-sensor fusion
- [ ] Advanced safety testing
- [ ] Performance optimization
- [ ] User interface development

### Phase 4: Advanced Features (Q3-Q4 2026)
- [ ] Cloud connectivity
- [ ] Multi-robot coordination
- [ ] Learning capabilities
- [ ] Commercial deployment

## Safety Philosophy

**Safety First**: BuddyBot prioritizes human safety above all other system capabilities. The robot must never cause harm to humans or property, even at the expense of functionality.

### Safety Principles
- **Defense in Depth**: Multiple independent safety layers
- **Fail-Safe Defaults**: Safest possible state when systems fail
- **Transparent Operation**: Safety status always visible and logged
- **Conservative Design**: Safety margins exceed requirements

### Safety Layers
1. **Hardware Layer**: Physical E-stop, motor driver safeties
2. **Firmware Layer**: Pico watchdog, command validation
3. **Software Layer**: ROS safety supervisor, collision detection
4. **System Layer**: Command arbitration, mode management

### Safety Verification
- **Testing**: Comprehensive safety system validation
- **Monitoring**: Continuous safety status reporting
- **Training**: Operator safety procedures and emergency protocols
- **Documentation**: Complete safety analysis and procedures

## Contributing

This is a capstone project demonstrating robotics engineering principles. Contributions should:

1. Follow ROS 2 best practices and safety guidelines
2. Include comprehensive testing, especially safety systems
3. Update documentation for any architectural changes
4. Maintain the Brain vs Spinal Cord separation of concerns

## License

Apache 2.0 - See LICENSE file for details.

## Acknowledgments

- Raspberry Pi Foundation for hardware platforms
- ROS 2 community for the robotics framework
- Open source computer vision and navigation communities
- Capstone project advisors and mentors

## Documentation

- [System Architecture](docs/architecture.md)
- [Safety Policy](docs/safety_policy.md)
- [UART Protocol](docs/uart_protocol.md)
- [Development Plan](docs/development_plan.md)