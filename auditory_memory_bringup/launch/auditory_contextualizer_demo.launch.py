from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    ltm_path = LaunchConfiguration('ltm_path')
    start_rqt = LaunchConfiguration('start_rqt')

    auditory_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('auditory_memory_bringup'),
                'launch',
                'auditory_memory.launch.py',
            ])
        ),
        launch_arguments={
            'ltm_path': ltm_path,
            'start_rqt': start_rqt,
            'start_risk_bridge': 'true',
        }.items(),
    )

    contextualizer_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([
                FindPackageShare('cs4home_contextualizer_module'),
                'launch',
                'launch_contextualizer.launch.py',
            ])
        ),
    )

    lifecycle_steps = [
        TimerAction(
            period=2.0,
            actions=[ExecuteProcess(
                cmd=['ros2', 'lifecycle', 'set', '/contextualizer_module', 'configure'],
                output='screen',
            )],
        ),
        TimerAction(
            period=3.0,
            actions=[ExecuteProcess(
                cmd=['ros2', 'lifecycle', 'set', '/risk_assesor_module', 'configure'],
                output='screen',
            )],
        ),
        TimerAction(
            period=4.0,
            actions=[ExecuteProcess(
                cmd=['ros2', 'lifecycle', 'set', '/contextualizer_module', 'activate'],
                output='screen',
            )],
        ),
        TimerAction(
            period=5.0,
            actions=[ExecuteProcess(
                cmd=['ros2', 'lifecycle', 'set', '/risk_assesor_module', 'activate'],
                output='screen',
            )],
        ),
    ]

    return LaunchDescription([
        DeclareLaunchArgument(
            'ltm_path',
            default_value='/home/lab/auditory_ws/auditory_memory_data/ltm.json',
            description='Path to the persistent long-term auditory memory JSON file.',
        ),
        DeclareLaunchArgument(
            'start_rqt',
            default_value='false',
            description='Start rqt with the auditory memory plugin.',
        ),
        auditory_launch,
        contextualizer_launch,
        *lifecycle_steps,
    ])
