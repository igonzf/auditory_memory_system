import time

import rclpy
from geometry_msgs.msg import Pose

from auditory_memory_msgs.msg import AuditoryObservation


POSES = {
    'living_room': (5.0, 2.0, 0.0),
    'kitchen': (2.0, 1.0, 0.0),
}


EVENTS = [
    (0, 'living_room', ['voices'],
     'person talking, first time heard today; expect high novelty and arousal rise'),
    (10, 'living_room', ['voices'],
     'same sound again; expect novelty to start dropping from repetition'),
    (20, 'living_room', ['tv_sound'],
     'TV on near voices context; expect living_room tv_sound edge'),
    (30, 'living_room', ['voices', 'tv_sound'],
     'both together; expect co-occurrence edge voices <-> tv_sound'),
    (50, 'living_room', ['voices', 'tv_sound'],
     'same pattern again; expect co-occurrence weight increase and lower arousal'),
    (70, 'kitchen', ['alarm'],
     'sudden alarm in another room; expect maximum novelty and alarm focus'),
    (85, 'kitchen', ['alarm'],
     'alarm again unresolved; expect arousal high and active alarm reinforced'),
    (100, 'living_room', ['voices', 'tv_sound'],
     'back to familiar pattern; expect arousal drop and visible contrast'),
]


def make_pose(room):
    x, y, z = POSES[room]
    pose = Pose()
    pose.position.x = x
    pose.position.y = y
    pose.position.z = z
    pose.orientation.w = 1.0
    return pose


def publish_event(node, pub, elapsed_s, room, sounds, note):
    for sound in sounds:
        msg = AuditoryObservation()
        msg.header.stamp = node.get_clock().now().to_msg()
        msg.header.frame_id = room
        msg.description = f'{room}: {" + ".join(sounds)}'
        msg.keywords = [sound, room, 'simple_sim']
        msg.pose = make_pose(room)
        pub.publish(msg)
    print(f'[SIMPLE SIM t={elapsed_s}s] {room.upper()} | {"+".join(sounds)} | {note}', flush=True)


def main(args=None):
    rclpy.init(args=args)
    node = rclpy.create_node('simple_audio_simulator')
    node.declare_parameter('publish_topic', '/sound_observation')
    topic = node.get_parameter('publish_topic').get_parameter_value().string_value
    pub = node.create_publisher(AuditoryObservation, topic, 10)
    start = time.monotonic()

    try:
        for elapsed_s, room, sounds, note in EVENTS:
            while rclpy.ok() and time.monotonic() - start < elapsed_s:
                try:
                    rclpy.spin_once(node, timeout_sec=0.05)
                except Exception:
                    if not rclpy.ok():
                        return
                    raise
            if not rclpy.ok():
                break
            publish_event(node, pub, elapsed_s, room, sounds, note)
            try:
                rclpy.spin_once(node, timeout_sec=0.1)
            except Exception:
                if not rclpy.ok():
                    return
                raise
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
