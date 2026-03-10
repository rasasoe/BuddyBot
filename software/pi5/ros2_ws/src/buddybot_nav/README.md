# buddybot_nav

LiDAR-based navigation stack for BuddyBot with semantic waypoint management.

## Overview

This package provides autonomous navigation capabilities for BuddyBot using:
- **LiDAR-based SLAM**: Real-time mapping and localization
- **Waypoint Navigation**: Semantic destination management
- **Nav2 Integration**: ROS 2 Navigation stack
- **Safety Integration**: Emergency stop and collision avoidance

## Architecture

### Separation of Concerns
- **Global Navigation** (this package): Long-range path planning using LiDAR
- **Local Safety** (vision package): Immediate collision avoidance using camera
- **Command Arbitration** (system package): Priority-based command selection

### Key Components

#### Waypoint Manager Node (`waypoint_manager_node.py`)
- **Purpose**: High-level navigation interface
- **Features**:
  - Semantic waypoint database management
  - Nav2 action client integration
  - Navigation status monitoring
  - System mode coordination

#### Configuration Files
- **`config/waypoints.yaml`**: Semantic waypoint definitions
- **`config/nav_params.yaml`**: Navigation stack parameters

## Integration Points

### Nav2 Navigation Stack
```
Waypoint Manager → Nav2 Action Server (navigate_to_pose)
                    ↓
               Path Planning → Controller → cmd_vel
```

### System Integration
```
System Mode Manager → Waypoint Manager (navigation enable/disable)
Safety Supervisor → Navigation Stack (emergency stop)
Command Multiplexer → Navigation cmd_vel (when NAVIGATION mode active)
```

### Topic Interfaces

#### Published Topics
- `/nav/current_waypoint` (std_msgs/String): Current navigation target
- `/nav/navigation_status` (std_msgs/String): Navigation state feedback

#### Subscribed Topics
- `/odom` (nav_msgs/Odometry): Robot odometry for progress monitoring
- `/system/current_mode` (std_msgs/String): System mode coordination
- `/system/safety_active` (std_msgs/Bool): Emergency stop integration

#### Services
- `/nav/waypoint_request` (std_srvs/Trigger): Request navigation to waypoint
- `/nav/get_waypoints` (std_srvs/Trigger): List available waypoints
- `/nav/cancel_navigation` (std_srvs/Trigger): Cancel current navigation

### Nav2 Action Interface
- **Action Server**: `/navigate_to_pose` (nav2_msgs/NavigateToPose)
- **Goal**: PoseStamped target in map frame
- **Feedback**: Navigation progress and ETA
- **Result**: Success/failure status

## Waypoint System

### Semantic Destinations
Waypoints are defined with semantic names that map to physical poses:

```yaml
waypoints:
  kitchen:
    pose:
      x: 4.0
      y: 2.0
      theta: 0.0
    description: "Kitchen counter area"
```

### Usage Examples
```bash
# Navigate to kitchen
rosservice call /nav/waypoint_request "kitchen"

# Get available waypoints
rosservice call /nav/get_waypoints

# Cancel navigation
rosservice call /nav/cancel_navigation
```

## System Mode Integration

The navigation system integrates with BuddyBot's mode management:

- **IDLE**: Navigation disabled
- **MANUAL**: Navigation disabled, manual control active
- **FOLLOW**: Navigation disabled, person following active
- **NAVIGATION**: Navigation enabled, waypoint following active

Mode changes automatically cancel active navigation when switching away from NAVIGATION mode.

## Safety Integration

### Emergency Stop
- Monitors `/system/safety_active` topic
- Immediately cancels navigation on safety trigger
- Integrates with Nav2 recovery behaviors

### Collision Avoidance
- **Global**: Nav2 costmaps prevent path planning through obstacles
- **Local**: Vision system provides immediate collision avoidance
- **Safety Supervisor**: System-wide safety state coordination

## Configuration

### Waypoint Database (`config/waypoints.yaml`)
- Define semantic waypoints with poses
- Include approach parameters and descriptions
- Support for waypoint sequences (multi-stop navigation)

### Navigation Parameters (`config/nav_params.yaml`)
- SLAM and localization settings
- Path planning parameters
- Robot physical constraints
- Safety and recovery configurations

## Launch Configuration

### Basic Navigation
```bash
ros2 launch buddybot_nav nav.launch.py slam:=false
```

### Mapping Mode
```bash
ros2 launch buddybot_nav nav.launch.py slam:=true
```

### Parameters
- `use_sim_time`: Use simulation time (default: false)
- `slam`: Enable SLAM mapping (default: false)
- `nav_params`: Path to navigation parameters
- `waypoints`: Path to waypoint configuration

## Dependencies

- `rclpy`: ROS 2 Python client
- `nav2_msgs`: Nav2 action interfaces
- `nav_msgs`: Navigation messages
- `geometry_msgs`: Geometric primitives
- `buddybot_msgs`: Custom BuddyBot messages

## Future Enhancements

- Multi-waypoint sequences
- Dynamic waypoint addition/removal
- Navigation learning from user preferences
- Integration with voice commands
- Advanced recovery behaviors