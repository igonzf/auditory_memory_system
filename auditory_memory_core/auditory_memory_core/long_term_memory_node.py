import json
import os

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from auditory_memory_core.memory import LongTermMemory, stamp_to_sec
from auditory_memory_msgs.msg import AuditoryEpisode


class LongTermMemoryNode(Node):
    def __init__(self):
        super().__init__('long_term_memory_node')

        self.declare_parameter('consolidation_topic', '/auditory_memory/consolidation')
        self.declare_parameter('ltm_patterns_topic', '/auditory_memory/ltm_patterns')
        self.declare_parameter('ltm_path', '/tmp/auditory_ltm.json')
        self.declare_parameter('ltm_serialize_interval_s', 30.0)
        self.declare_parameter('ltm_prune_min_weight', 0.02)
        self.declare_parameter('ltm_prune_older_than_s', 30.0 * 24.0 * 3600.0)
        self.declare_parameter('unknown_location_label', 'unknown_location')
        self.declare_parameter('learn_unknown_location_patterns', False)
        self.declare_parameter('location_missing_neutral_congruence', 0.5)

        ltm_path = self.get_parameter('ltm_path').get_parameter_value().string_value
        self.ltm = LongTermMemory(
            ltm_path,
            unknown_location_label=self.get_parameter(
                'unknown_location_label').get_parameter_value().string_value,
            learn_unknown_location_patterns=bool(
                self.get_parameter('learn_unknown_location_patterns').value),
            location_missing_neutral_congruence=float(
                self.get_parameter('location_missing_neutral_congruence').value),
        )
        self.dirty = False
        self._log_ltm_startup(ltm_path)
        self.sub = self.create_subscription(
            AuditoryEpisode,
            self.get_parameter('consolidation_topic').get_parameter_value().string_value,
            self.consolidation_cb,
            10)
        self.pattern_pub = self.create_publisher(
            String,
            self.get_parameter('ltm_patterns_topic').get_parameter_value().string_value,
            10)
        self.timer = self.create_timer(
            max(1.0, float(self.get_parameter('ltm_serialize_interval_s').value)),
            self.timer_cb)
        self.pattern_timer = self.create_timer(1.0, self.publish_patterns)

    def consolidation_cb(self, msg: AuditoryEpisode) -> None:
        updates = self.ltm.consolidate_episode(
            sound_type=msg.sound_type,
            location_id=msg.location_id,
            started_at_s=stamp_to_sec(msg.started_at),
            last_heard_s=stamp_to_sec(msg.last_heard),
            co_occurring_sounds=msg.co_occurring_sounds,
            novelty=float(msg.novelty),
        )
        self._log_pattern_updates(updates)
        self.dirty = True
        self.publish_patterns()

    def timer_cb(self) -> None:
        self.ltm.prune(
            min_weight=float(self.get_parameter('ltm_prune_min_weight').value),
            older_than_s=float(self.get_parameter('ltm_prune_older_than_s').value),
        )
        if self.dirty:
            self.ltm.save()
            self.dirty = False
        self.publish_patterns()

    def publish_patterns(self) -> None:
        msg = String()
        msg.data = json.dumps(self.ltm.pattern_summary(limit=5), sort_keys=True)
        self.pattern_pub.publish(msg)

    def _log_pattern_updates(self, updates) -> None:
        for update in updates:
            if update.get('type') == 'sound_location':
                self.get_logger().info(
                    f"LTM pattern updated: {update.get('sound')} -> {update.get('location')} "
                    f"weight={float(update.get('weight', 0.0)):.2f} count={int(update.get('count', 0))}")
            elif update.get('type') == 'co_occurrence':
                self.get_logger().info(
                    f"LTM pattern updated: {update.get('sound_a')} <-> {update.get('sound_b')} "
                    f"weight={float(update.get('weight', 0.0)):.2f} count={int(update.get('count', 0))}")
            elif update.get('type') == 'time':
                self.get_logger().info(
                    f"LTM time pattern updated: {update.get('sound')} -> {update.get('period')} "
                    f"count={int(update.get('count', 0))}")

    def _log_ltm_startup(self, ltm_path: str) -> None:
        summary = self.ltm.summary_counts()
        expanded_path = os.path.expanduser(ltm_path)
        self.get_logger().info(
            f'Long-Term Memory using LTM path: {expanded_path} '
            f'(exists={os.path.exists(expanded_path)})')
        self.get_logger().info(
            'Loaded LTM: '
            f"{summary['sounds']} sounds, {summary['locations']} locations, "
            f"{summary['sound_location_patterns']} sound-location patterns, "
            f"{summary['co_occurrence_patterns']} co-occurrence patterns, "
            f"{summary['time_patterns']} time patterns, "
            f"{summary['nodes']} nodes, {summary['edges']} edges")

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
