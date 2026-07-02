import json
from typing import Dict, List

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from auditory_memory_core.memory import LongTermMemory, WorkingMemory, sec_to_stamp, stamp_to_sec
from auditory_memory_msgs.msg import (
    AuditoryEpisode,
    AuditoryObservation,
    AuditoryWorkingMemoryState,
)

try:
    import yaml
except ImportError:  # pragma: no cover - optional robot deployment dependency
    yaml = None


class WorkingMemoryNode(Node):
    def __init__(self):
        super().__init__('working_memory_node')

        self.declare_parameter('observation_topic', '/sound_observation')
        self.declare_parameter('state_topic', '/auditory_memory/wm_state')
        self.declare_parameter('graph_viz_topic', '/auditory_memory/graph_viz')
        self.declare_parameter('consolidation_topic', '/auditory_memory/consolidation')
        self.declare_parameter('timer_hz', 5.0)

        self.declare_parameter('active_gap_s', 1.0)
        self.declare_parameter('inactive_gap_s', 5.0)
        self.declare_parameter('episode_ttl_s', 600.0)
        self.declare_parameter('co_occurrence_window_s', 2.0)
        self.declare_parameter('arousal_decay', 0.05)
        self.declare_parameter('context_urgency_enabled', True)
        self.declare_parameter('context_urgency_window_s', 1200.0)
        self.declare_parameter('context_urgency_min_delay_s', 1.0)
        self.declare_parameter('context_urgency_novelty_threshold', 0.70)
        self.declare_parameter('context_urgency_same_location_only', True)
        self.declare_parameter('context_urgency_boost', 0.25)
        self.declare_parameter('context_urgency_focus_weight', 0.25)
        self.declare_parameter('arousal_debug_logs', False)

        self.declare_parameter('ltm_path', '/tmp/auditory_ltm.json')
        self.declare_parameter('location_config_path', '')

        self.locations = self._load_locations(
            self.get_parameter('location_config_path').get_parameter_value().string_value)
        self.ltm = LongTermMemory(self.get_parameter('ltm_path').get_parameter_value().string_value)
        self.memory = WorkingMemory(self.ltm)
        self.logical_now_s = self.get_clock().now().nanoseconds / 1e9

        self.observation_sub = self.create_subscription(
            AuditoryObservation,
            self.get_parameter('observation_topic').get_parameter_value().string_value,
            self.sound_observation_cb,
            10)
        self.state_pub = self.create_publisher(
            AuditoryWorkingMemoryState,
            self.get_parameter('state_topic').get_parameter_value().string_value,
            10)
        self.graph_pub = self.create_publisher(
            String,
            self.get_parameter('graph_viz_topic').get_parameter_value().string_value,
            10)
        self.consolidation_pub = self.create_publisher(
            AuditoryEpisode,
            self.get_parameter('consolidation_topic').get_parameter_value().string_value,
            10)

        timer_hz = float(self.get_parameter('timer_hz').value)
        self.last_timer_s = None
        self.timer = self.create_timer(1.0 / max(timer_hz, 0.1), self.timer_cb)

    def sound_observation_cb(self, msg: AuditoryObservation) -> None:
        sound_type = self._build_sound_type(msg)
        location_id = self._location_for_pose(msg)
        timestamp_s = stamp_to_sec(msg.header.stamp)
        if timestamp_s <= 0.0:
            timestamp_s = self.get_clock().now().nanoseconds / 1e9
        self.logical_now_s = max(self.logical_now_s, timestamp_s)
        self._sync_memory_parameters()
        self.memory.observe(sound_type, location_id, timestamp_s)
        self._log_arousal_evidence()
        if bool(self.get_parameter('arousal_debug_logs').value):
            self.get_logger().info(
                f'Observed {sound_type} in {location_id}: '
                f'arousal={self.memory.arousal_level:.3f}')
        self._log_context_urgency_if_applied()
        self._log_focus_if_changed()

    def timer_cb(self) -> None:
        wall_now_s = self.get_clock().now().nanoseconds / 1e9
        now_s = max(wall_now_s, self.logical_now_s)
        if self.last_timer_s is None:
            self.last_timer_s = wall_now_s
            return
        dt_s = max(0.0, wall_now_s - self.last_timer_s)
        self.last_timer_s = wall_now_s

        ready_episode_ids = self.memory.update(
            now_s=now_s,
            dt_s=dt_s,
            arousal_decay=float(self.get_parameter('arousal_decay').value),
            inactive_gap_s=float(self.get_parameter('inactive_gap_s').value),
        )
        for episode_id in ready_episode_ids:
            episode_msg = self._episode_msg(episode_id, now_s)
            episode_msg.consolidation_ready = True
            self.ltm.consolidate_episode(
                sound_type=episode_msg.sound_type,
                location_id=episode_msg.location_id,
                started_at_s=stamp_to_sec(episode_msg.started_at),
                last_heard_s=stamp_to_sec(episode_msg.last_heard),
                co_occurring_sounds=episode_msg.co_occurring_sounds,
                novelty=float(episode_msg.novelty),
            )
            self.consolidation_pub.publish(episode_msg)
            self.memory.mark_consolidated(episode_id)

        self.memory.forget_old_episodes(
            now_s,
            float(self.get_parameter('episode_ttl_s').value),
        )
        self._publish_state(now_s)
        self._publish_graph_viz()
        if bool(self.get_parameter('arousal_debug_logs').value):
            self.get_logger().info(
                f'Published arousal: wm_state/graph_viz={self.memory.arousal_level:.3f}, '
                f'decay_dt_wall_s={dt_s:.3f}, logical_now_s={now_s:.3f}')
        self._log_focus_if_changed()

    def _sync_memory_parameters(self) -> None:
        self.memory.co_occurrence_window_s = float(self.get_parameter('co_occurrence_window_s').value)
        self.memory.context_urgency_enabled = bool(self.get_parameter('context_urgency_enabled').value)
        self.memory.context_urgency_window_s = float(self.get_parameter('context_urgency_window_s').value)
        self.memory.context_urgency_min_delay_s = float(
            self.get_parameter('context_urgency_min_delay_s').value)
        self.memory.context_urgency_novelty_threshold = float(
            self.get_parameter('context_urgency_novelty_threshold').value)
        self.memory.context_urgency_same_location_only = bool(
            self.get_parameter('context_urgency_same_location_only').value)
        self.memory.context_urgency_boost = float(self.get_parameter('context_urgency_boost').value)
        self.memory.context_urgency_focus_weight = float(
            self.get_parameter('context_urgency_focus_weight').value)

    def _log_context_urgency_if_applied(self) -> None:
        info = self.memory.last_context_urgency_info
        if not info:
            return
        self.get_logger().info(
            'Context urgency boost: '
            f"{info['sound_type']} in {info['location_id']} occurred "
            f"{info['elapsed_s']:.0f}s after high-novelty "
            f"{info['source_sound_type']} in {info['source_location_id']} "
            f"(source novelty={info['source_novelty']:.2f}, "
            f"urgency={info['contextual_urgency']:.2f})")

    def _log_arousal_evidence(self) -> None:
        info = self.memory.last_arousal_evidence_info
        if not info:
            return
        self.get_logger().info(
            f"Arousal evidence for {info['sound_type']} in {info['location_id']}: "
            f"novelty={info['novelty']:.2f}, "
            f"contextual_urgency={info['contextual_urgency']:.2f}, "
            f"contribution={info['contribution']:.2f}")

    def _log_focus_if_changed(self) -> None:
        info = self.memory.last_focus_info
        if not info:
            return
        self.get_logger().info(
            f"Focus selected: {info['sound_type']} in {info['location_id']} | "
            f"novelty={info['novelty']:.2f} | "
            f"incongruence={info['incongruence']:.2f} | "
            f"contextual_urgency={info['contextual_urgency']:.2f} | "
            f"score={info['score']:.2f}")
        self.memory.last_focus_info = None

    def _publish_state(self, now_s: float) -> None:
        focused_sound, focused_location = self.memory.focused_sound_location()
        state = AuditoryWorkingMemoryState()
        state.header.stamp = self.get_clock().now().to_msg()
        state.header.frame_id = 'map'
        state.active_episodes = [
            self._episode_msg(episode_id, now_s)
            for episode_id in self.memory.active_episode_ids()
        ]
        state.focused_sound = focused_sound
        state.focused_location = focused_location
        state.arousal_level = float(self.memory.arousal_level)
        self.state_pub.publish(state)

    def _publish_graph_viz(self) -> None:
        msg = String()
        msg.data = json.dumps(self.memory.graph_viz(), sort_keys=True)
        self.graph_pub.publish(msg)

    def _episode_msg(self, episode_id: str, now_s: float) -> AuditoryEpisode:
        attrs = self.memory.episode_attrs(episode_id)
        msg = AuditoryEpisode()
        msg.header.stamp = sec_to_stamp(float(attrs.get('last_heard', now_s)))
        msg.header.frame_id = 'map'
        msg.episode_id = episode_id
        msg.sound_type = attrs.get('sound_type', '')
        msg.location_id = attrs.get('location_id', '')
        msg.co_occurring_sounds = list(attrs.get('co_occurring_sounds', []))
        msg.intensity = float(attrs.get('intensity', 0.0))
        msg.novelty = float(attrs.get('novelty', 0.0))
        msg.location_congruence = float(attrs.get('location_congruence', 0.0))
        msg.arousal_contribution = float(attrs.get('arousal_contribution', 0.0))
        msg.consolidation_ready = bool(attrs.get('consolidation_ready', False))
        msg.started_at = sec_to_stamp(float(attrs.get('started_at', now_s)))
        msg.last_heard = sec_to_stamp(float(attrs.get('last_heard', now_s)))
        return msg

    def _build_sound_type(self, msg: AuditoryObservation) -> str:
        if msg.keywords:
            return msg.keywords[0].strip().lower().replace(' ', '_') or 'unknown'
        if msg.description:
            return msg.description.strip().lower().replace(' ', '_')[:48] or 'unknown'
        return 'unknown'

    def _location_for_pose(self, msg: AuditoryObservation) -> str:
        x = float(msg.pose.position.x)
        y = float(msg.pose.position.y)
        for location in self.locations:
            if location['x_min'] <= x <= location['x_max'] and location['y_min'] <= y <= location['y_max']:
                return location['id']
        return msg.header.frame_id or 'unknown'

    def _load_locations(self, path: str) -> List[Dict[str, float]]:
        if not path:
            return []
        if yaml is None:
            self.get_logger().warning('PyYAML is not available; location_config_path ignored')
            return []
        try:
            with open(path, 'r', encoding='utf-8') as stream:
                data = yaml.safe_load(stream) or {}
        except OSError as exc:
            self.get_logger().warning(f'Could not read location config {path}: {exc}')
            return []

        rooms = data.get('rooms', data if isinstance(data, list) else [])
        locations = []
        for item in rooms:
            if not isinstance(item, dict):
                continue
            bounds = item.get('bounds', item)
            try:
                locations.append({
                    'id': str(item.get('id', item.get('name'))),
                    'x_min': float(bounds['x_min']),
                    'x_max': float(bounds['x_max']),
                    'y_min': float(bounds['y_min']),
                    'y_max': float(bounds['y_max']),
                })
            except (KeyError, TypeError, ValueError):
                self.get_logger().warning(f'Ignoring invalid location entry: {item}')
        return [loc for loc in locations if loc['id'] and loc['id'] != 'None']


def main(args=None):
    rclpy.init(args=args)
    node = WorkingMemoryNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
