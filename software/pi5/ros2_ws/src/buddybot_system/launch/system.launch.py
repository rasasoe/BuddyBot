#!/usr/bin/env python3
"""System launch file for BuddyBot."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    use_sim_time_arg = DeclareLaunchArgument(
        "use_sim_time",
        default_value="false",
        description="Use simulation time",
    )

    command_timeout_arg = DeclareLaunchArgument(
        "command_timeout",
        default_value="1.0",
        description="Command timeout in seconds",
    )

    safety_latch_time_arg = DeclareLaunchArgument(
        "safety_latch_time",
        default_value="2.0",
        description="Safety latch duration in seconds",
    )

    command_mux_node = Node(
        package="buddybot_system",
        executable="command_mux_node",
        name="command_mux_node",
        output="screen",
        parameters=[
            {"use_sim_time": LaunchConfiguration("use_sim_time")},
            {"command_timeout": LaunchConfiguration("command_timeout")},
        ],
    )

    mode_manager_node = Node(
        package="buddybot_system",
        executable="mode_manager_node",
        name="mode_manager_node",
        output="screen",
        parameters=[{"use_sim_time": LaunchConfiguration("use_sim_time")}],
    )

    safety_supervisor_node = Node(
        package="buddybot_system",
        executable="safety_supervisor_node",
        name="safety_supervisor_node",
        output="screen",
        parameters=[
            {"use_sim_time": LaunchConfiguration("use_sim_time")},
            {"command_timeout": LaunchConfiguration("command_timeout")},
            {"safety_latch_time": LaunchConfiguration("safety_latch_time")},
        ],
    )

    lidar_avoidance_node = Node(
        package="buddybot_system",
        executable="lidar_avoidance_node",
        name="lidar_avoidance_node",
        output="screen",
        parameters=[{"use_sim_time": LaunchConfiguration("use_sim_time")}],
    )

    return LaunchDescription(
        [
            use_sim_time_arg,
            command_timeout_arg,
            safety_latch_time_arg,
            command_mux_node,
            mode_manager_node,
            safety_supervisor_node,
            lidar_avoidance_node,
        ]
    )
