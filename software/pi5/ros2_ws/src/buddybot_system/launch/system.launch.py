#!/usr/bin/env python3
"""
System Launch File for BuddyBot

This launch file starts all system-level nodes for BuddyBot:
- Command Multiplexer: Routes commands based on priority
- Mode Manager: Manages system operating modes
- Safety Supervisor: Monitors safety conditions

Architecture:
- All nodes run in the same process group for coordinated shutdown
- Safety supervisor has highest priority monitoring
- Command multiplexer coordinates with mode manager
- Comprehensive logging and monitoring enabled

Parameters:
- use_sim_time: Use simulation time (default: false)
- log_level: ROS logging level (default: info)
- command_timeout: Command timeout in seconds (default: 1.0)
- safety_latch_time: Safety latch duration (default: 2.0)

Node Configuration:
- command_mux_node: Priority-based command routing
- mode_manager_node: System mode coordination
- safety_supervisor_node: Safety monitoring and override
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, LogInfo
from launch.substitutions import LaunchConfiguration, TextSubstitution
from launch_ros.actions import Node, PushRosNamespace
from launch_ros.descriptions import ParameterFile
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """Generate launch description for BuddyBot system nodes."""

    # Package directories
    pkg_system = get_package_share_directory('buddybot_system')

    # Launch arguments
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation time'
    )

    log_level_arg = DeclareLaunchArgument(
        'log_level',
        default_value='info',
        description='ROS logging level'
    )

    command_timeout_arg = DeclareLaunchArgument(
        'command_timeout',
        default_value='1.0',
        description='Command timeout in seconds'
    )

    safety_latch_time_arg = DeclareLaunchArgument(
        'safety_latch_time',
        default_value='2.0',
        description='Safety latch duration in seconds'
    )

    # Common parameters for all nodes
    common_params = [
        {'use_sim_time': LaunchConfiguration('use_sim_time')},
        {'log_level': LaunchConfiguration('log_level')}
    ]

    # Command Multiplexer Node
    command_mux_node = Node(
        package='buddybot_system',
        executable='command_mux_node.py',
        name='command_mux_node',
        output='screen',
        parameters=common_params + [
            {'command_timeout': LaunchConfiguration('command_timeout')}
        ],
        remappings=[
            ('/system/command_mux/input/manual', '/control/manual/cmd_vel'),
            ('/system/command_mux/input/follow', '/vision/follow/cmd_vel'),
            ('/system/command_mux/input/nav', '/nav/cmd_vel'),
            ('/system/command_mux/input/safety', '/system/safety/cmd_vel'),
            ('/system/command_mux/output', '/buddybot/cmd_vel')
        ]
    )

    # Mode Manager Node
    mode_manager_node = Node(
        package='buddybot_system',
        executable='mode_manager_node.py',
        name='mode_manager_node',
        output='screen',
        parameters=common_params,
        remappings=[
            ('/system/mode_manager/mode_request', '/system/mode_request'),
            ('/system/mode_manager/current_mode', '/system/current_mode'),
            ('/system/mode_manager/safety_active', '/system/safety_active')
        ]
    )

    # Safety Supervisor Node
    safety_supervisor_node = Node(
        package='buddybot_system',
        executable='safety_supervisor_node.py',
        name='safety_supervisor_node',
        output='screen',
        parameters=common_params + [
            {'command_timeout': LaunchConfiguration('command_timeout')},
            {'safety_latch_time': LaunchConfiguration('safety_latch_time')}
        ],
        remappings=[
            ('/system/estop', '/system/estop'),
            ('/buddybot/pico_safety_event', '/buddybot/pico_safety_event'),
            ('/vision/ttc_alert', '/vision/ttc_alert'),
            ('/system/command_status', '/system/command_status'),
            ('/system/safety_active', '/system/safety_active'),
            ('/system/safety_status', '/system/safety_status')
        ]
    )

    # System group - all nodes run together
    system_group = GroupAction([
        PushRosNamespace('system'),
        LogInfo(msg='Starting BuddyBot System Nodes...'),
        command_mux_node,
        mode_manager_node,
        safety_supervisor_node,
        LogInfo(msg='BuddyBot System Nodes Started Successfully')
    ])

    # Launch description
    ld = LaunchDescription()

    # Add launch arguments
    ld.add_action(use_sim_time_arg)
    ld.add_action(log_level_arg)
    ld.add_action(command_timeout_arg)
    ld.add_action(safety_latch_time_arg)

    # Add system group
    ld.add_action(system_group)

    return ld