import rclpy
from rclpy.node import Node

from auditory_memory_core.memory import LongTermMemory, stamp_to_sec
from auditory_memory_msgs.msg import AuditoryEpisode


class LongTermMemoryNode(Node):
    def __init__(self):
        super().__init__('long_term_memory_node')

        self.declare_parameter('consolidation_topic', '/auditory_memory/consolidation')
        self.declare_parameter('ltm_path', '/tmp/auditory_ltm.json')
        self.declare_parameter('ltm_serialize_interval_s', 30.0)
        self.declare_parameter('ltm_prune_min_weight', 0.02)
        self.declare_parameter('ltm_prune_older_than_s', 30.0 * 24.0 * 3600.0)

        self.ltm = LongTermMemory(self.get_parameter('ltm_path').get_parameter_value().string_value)
        self.dirty = False
        self.sub = self.create_subscription(
            AuditoryEpisode,
            self.get_parameter('consolidation_topic').get_parameter_value().string_value,
            self.consolidation_cb,
            10)
        self.timer = self.create_timer(
            max(1.0, float(self.get_parameter('ltm_serialize_interval_s').value)),
            self.timer_cb)

    def consolidation_cb(self, msg: AuditoryEpisode) -> None:
        self.ltm.consolidate_episode(
            sound_type=msg.sound_type,
            location_id=msg.location_id,
            started_at_s=stamp_to_sec(msg.started_at),
            last_heard_s=stamp_to_sec(msg.last_heard),
            co_occurring_sounds=msg.co_occurring_sounds,
            novelty=float(msg.novelty),
        )
        self.dirty = True

    def timer_cb(self) -> None:
        self.ltm.prune(
            min_weight=float(self.get_parameter('ltm_prune_min_weight').value),
            older_than_s=float(self.get_parameter('ltm_prune_older_than_s').value),
        )
        if self.dirty:
            self.ltm.save()
            self.dirty = False

    def close(self) -> None:
        if self.dirty:
            self.ltm.save()
            self.dirty = False


def main(args=None):
    rclpy.init(args=args)
    node = LongTermMemoryNode()
    try:
        rclpy.spin(node)
    finally:
        node.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
