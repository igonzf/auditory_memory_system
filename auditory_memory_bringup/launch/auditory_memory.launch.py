from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    ltm_path = LaunchConfiguration('ltm_path')
    start_rqt = LaunchConfiguration('start_rqt')

    return LaunchDescription([
        DeclareLaunchArgument(
            'ltm_path',
            default_value='/home/lab/auditory_ws/auditory_memory_data/ltm.json',
            description='Path to the persistent long-term auditory memory JSON file.'),
        DeclareLaunchArgument(
            'start_rqt',
            default_value='true',
            description='Start rqt directly with the auditory memory plugin loaded.'),

        Node(
            package='auditory_memory_core',
            executable='long_term_memory_node',
            name='long_term_memory_node',
            output='screen',
            parameters=[{
                'ltm_path': ltm_path,
            }]),

        Node(
            package='auditory_memory_core',
            executable='working_memory_node',
            name='working_memory_node',
            output='screen',
            parameters=[{
                'ltm_path': ltm_path,
                'state_topic': '/auditory_memory/wm_state',
                'graph_viz_topic': '/auditory_memory/graph_viz',
            }]),

        Node(
            package='rqt_gui',
            executable='rqt_gui',
            name='auditory_memory_rqt',
            output='screen',
            condition=IfCondition(start_rqt),
            arguments=[
                '--standalone',
                'auditory_memory_core.auditory_memory_plugin.AuditoryMemoryPlugin',
            ]),
    ])
