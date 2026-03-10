#!/usr/bin/env python3
"""
Navigation Launch File for BuddyBot

This launch file starts the navigation stack for BuddyBot:
- Waypoint Manager Node: Semantic navigation interface
- Nav2 Navigation Stack: Path planning and execution
- SLAM Toolbox: LiDAR-based mapping and localization

Architecture:
- Integrates with system command multiplexer
- Respects safety supervisor states
- Provides waypoint-based navigation services
- Supports both mapping and navigation modes

Integration Points:
- Command Mux: Navigation cmd_vel output when active
- System Modes: NAVIGATION mode coordination
- Safety Supervisor: Emergency stop integration
- Vision System: Local collision avoidance complement

Parameters:
- use_sim_time: Use simulation time (default: false)
- slam: Enable SLAM mapping (default: false)
- nav_params: Navigation parameter file path
- waypoints: Waypoint configuration file path

Node Configuration:
- waypoint_manager_node: High-level navigation interface
- nav2_bringup: Full Nav2 navigation stack
- slam_toolbox: LiDAR SLAM when mapping
"""

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration, TextSubstitution, PathJoinSubstitution
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node, PushRosNamespace
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    """Generate launch description for BuddyBot navigation stack."""

    # Package directories
    pkg_nav = get_package_share_directory('buddybot_nav')
    pkg_nav2 = get_package_share_directory('nav2_bringup')

    # Launch arguments
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation time'
    )

    slam_arg = DeclareLaunchArgument(
        'slam',
        default_value='false',
        description='Enable SLAM mapping mode'
    )

    nav_params_arg = DeclareLaunchArgument(
        'nav_params',
        default_value=os.path.join(pkg_nav, 'config', 'nav_params.yaml'),
        description='Navigation parameters file'
    )

    waypoints_arg = DeclareLaunchArgument(
        'waypoints',
        default_value=os.path.join(pkg_nav, 'config', 'waypoints.yaml'),
        description='Waypoints configuration file'
    )

    # Waypoint Manager Node
    waypoint_manager_node = Node(
        package='buddybot_nav',
        executable='waypoint_manager_node.py',
        name='waypoint_manager_node',
        output='screen',
        parameters=[
            {'use_sim_time': LaunchConfiguration('use_sim_time')},
            {'waypoint_config': LaunchConfiguration('waypoints')}
        ],
        remappings=[
            ('/nav/waypoint_request', '/nav/waypoint_request'),
            ('/nav/get_waypoints', '/nav/get_waypoints'),
            ('/nav/cancel_navigation', '/nav/cancel_navigation'),
            ('/nav/current_waypoint', '/nav/current_waypoint'),
            ('/nav/navigation_status', '/nav/navigation_status'),
            ('/system/current_mode', '/system/current_mode')
        ]
    )

    # Nav2 Navigation Stack
    # Note: This is a placeholder - actual Nav2 launch would include:
    # - nav2_bringup launch files
    # - SLAM toolbox when mapping
    # - Proper parameter files and remappings

    nav2_group = GroupAction([
        # Placeholder for Nav2 bringup
        # IncludeLaunchDescription(
        #     PythonLaunchDescriptionSource(
        #         os.path.join(pkg_nav2, 'launch', 'bringup_launch.py')
        #     ),
        #     launch_arguments={
        #         'use_sim_time': LaunchConfiguration('use_sim_time'),
        #         'params_file': LaunchConfiguration('nav_params'),
        #         'slam': LaunchConfiguration('slam')
        #     }.items()
        # )
    ])

    # Navigation group - all navigation nodes
    navigation_group = GroupAction([
        PushRosNamespace('nav'),
        waypoint_manager_node,
        nav2_group
    ])

    # Launch description
    ld = LaunchDescription()

    # Add launch arguments
    ld.add_action(use_sim_time_arg)
    ld.add_action(slam_arg)
    ld.add_action(nav_params_arg)
    ld.add_action(waypoints_arg)

    # Add navigation group
    ld.add_action(navigation_group)

    return ld