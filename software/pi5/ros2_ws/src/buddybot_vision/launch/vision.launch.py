from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    """Launch description for BuddyBot vision system."""

    # Camera node
    camera_node = Node(
        package='buddybot_vision',
        executable='camera_node',
        name='camera_node',
        parameters=[
            {'device': '/dev/video0'},
            {'width': 640},
            {'height': 480},
            {'fps': 30.0},
            {'publish_rate': 30.0}
        ]
    )

    # Person detector node
    detector_node = Node(
        package='buddybot_vision',
        executable='detector_node',
        name='detector_node',
        parameters=[
            {'model_config': 'models/mobilenet_ssd_v2_coco.pbtxt'},
            {'model_weights': 'models/mobilenet_ssd_v2_coco.pb'},
            {'confidence_threshold': 0.5},
            {'detection_interval': 5},
            {'publish_debug_image': False}
        ]
    )

    # Follow controller node
    follow_controller_node = Node(
        package='buddybot_vision',
        executable='follow_controller_node',
        name='follow_controller_node',
        parameters=[
            {'image_width': 640},
            {'image_height': 480},
            {'center_x_gain': 0.002},
            {'height_gain': 0.0005},
            {'target_height_ratio': 0.6},
            {'max_linear_velocity': 0.3},
            {'max_angular_velocity': 0.5}
        ]
    )

    # TTC node
    ttc_node = Node(
        package='buddybot_vision',
        executable='ttc_node',
        name='ttc_node',
        parameters=[
            {'ttc_threshold': 2.0},
            {'processing_interval': 3},
            {'min_features': 50}
        ]
    )

    return LaunchDescription([
        camera_node,
        detector_node,
        follow_controller_node,
        ttc_node
    ])