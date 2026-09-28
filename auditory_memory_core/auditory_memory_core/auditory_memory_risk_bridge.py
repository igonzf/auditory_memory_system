import os
import time
from typing import Dict, List

import rclpy
import yaml
from ament_index_python.packages import PackageNotFoundError, get_package_share_directory
from rclpy.node import Node

from auditory_memory_core.memory import stamp_to_sec
from auditory_memory_msgs.msg import AuditoryEpisode, AuditoryWorkingMemoryState
from cs4home_msgs.msg import ContextDescription, Entity


CONGRUENCE_THRESHOLD = 0.50


def default_config_path() -> str:
    try:
        share_dir = get_package_share_directory('auditory_memory_core')
        return os.path.join(share_dir, 'config', 'auditory_risk_demo_fmea.yaml')
    except PackageNotFoundError:
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config',
            'auditory_risk_demo_fmea.yaml',
        )


def load_config(path: str) -> Dict:
    with open(path, 'r', encoding='utf-8') as stream:
        return yaml.safe_load(stream) or {}


def clamp_score(value: float) -> int:
    return max(1, min(10, round(value)))


def period_label(timestamp_s: float) -> str:
    hour = time.localtime(timestamp_s).tm_hour
    if 5 <= hour < 12:
        return 'morning'
    if 12 <= hour < 17:
        return 'afternoon'
    if 17 <= hour < 22:
        return 'evening'
    return 'night'


def episode_timestamp_s(episode: AuditoryEpisode, fallback_s: float = 0.0) -> float:
    timestamp_s = stamp_to_sec(episode.last_heard)
    if timestamp_s <= 0.0:
        timestamp_s = stamp_to_sec(episode.started_at)
    if timestamp_s <= 0.0:
        timestamp_s = fallback_s
    return timestamp_s


def episode_context_key(episode: AuditoryEpisode, fallback_s: float = 0.0) -> str:
    timestamp_s = episode_timestamp_s(episode, fallback_s)
    return '|'.join((
        episode.sound_type or 'unknown_sound',
        episode.location_id or 'unknown_location',
        period_label(timestamp_s),
    ))


def proximity_from_depth(depth_m: float) -> str:
    if depth_m < 1.0:
        return 'very_close'
    if depth_m < 2.0:
        return 'close'
    if depth_m < 4.0:
        return 'medium'
    return 'far'


def build_entity_from_episode(
    episode: AuditoryEpisode,
    focused_sound: str,
    focused_location: str,
    config: Dict,
) -> Entity:
    adapter = config.get('memory_to_fmea', {})
    defaults = adapter.get('defaults', {})
    overrides = adapter.get('sound_overrides', {}).get(episode.sound_type, {})

    entity = Entity()
    entity.class_name = overrides.get('entity_type', episode.sound_type or 'audio_event')
    depth_m = float(overrides.get('depth_m', defaults.get('depth_m', 3.0)))
    entity.location.position.z = depth_m
    entity.location.orientation.w = 1.0
    entity.proximity_bin = proximity_from_depth(depth_m)
    entity.distance_to_robot = depth_m
    return entity


def is_risk_relevant(
    episode: AuditoryEpisode,
    min_novelty: float,
    max_location_congruence: float,
    min_arousal_contribution: float,
) -> bool:
    return any((
        float(episode.novelty) >= min_novelty,
        float(episode.location_congruence) <= max_location_congruence,
        float(episode.arousal_contribution) >= min_arousal_contribution,
    ))


def build_audio_context(
    state: AuditoryWorkingMemoryState,
    episodes: List[AuditoryEpisode],
    config: Dict,
) -> ContextDescription:
    msg = ContextDescription()
    msg.source = 'audio'
    if not episodes:
        msg.scene_description = 'Audio memory reports no risk-relevant active sound episodes.'
        return msg

    focused_episode = next(
        (
            episode for episode in episodes
            if episode.sound_type == state.focused_sound
            and episode.location_id == state.focused_location
        ),
        episodes[0],
    )
    timestamp_s = episode_timestamp_s(focused_episode, stamp_to_sec(state.header.stamp))
    if timestamp_s <= 0.0:
        timestamp_s = time.time()

    msg.entities = [
        build_entity_from_episode(
            episode,
            state.focused_sound,
            state.focused_location,
            config,
        )
        for episode in episodes
    ]
    evidence = []
    for episode in episodes:
        incongruent = float(episode.location_congruence) < CONGRUENCE_THRESHOLD
        focused = episode.sound_type == state.focused_sound and episode.location_id == state.focused_location
        evidence.append(
            f'{episode.sound_type} at {episode.location_id} '
            f'(novelty={float(episode.novelty):.2f}, '
            f'location_congruence={float(episode.location_congruence):.2f}, '
            f'arousal={float(episode.arousal_contribution):.2f}, '
            f'incongruent={str(incongruent).lower()}, focused={str(focused).lower()})')
    msg.scene_description = (
        f'Auditory memory context at {period_label(timestamp_s)}. '
        f'Focused sound: {state.focused_sound or "none"} in {state.focused_location or "unknown"}. '
        f'Arousal level: {float(state.arousal_level):.2f}. '
        f'Risk-relevant auditory evidence: {"; ".join(evidence)}.'
    )
    return msg


class AuditoryMemoryRiskBridge(Node):
    def __init__(self):
        super().__init__('auditory_memory_risk_bridge')
        self.declare_parameter('wm_state_topic', '/auditory_memory/wm_state')
        self.declare_parameter('context_topic', '/audio/context')
        self.declare_parameter('fmea_config', default_config_path())
        self.declare_parameter('publish_empty_context', False)
        self.declare_parameter('min_episode_novelty', 0.70)
        self.declare_parameter('max_location_congruence', 0.50)
        self.declare_parameter('min_arousal_contribution', 0.30)

        self.config_path = self.get_parameter('fmea_config').get_parameter_value().string_value
        self.config = load_config(self.config_path)
        self.published_context_keys = set()
        self.context_pub = self.create_publisher(
            ContextDescription,
            self.get_parameter('context_topic').get_parameter_value().string_value,
            10,
        )
        self.state_sub = self.create_subscription(
            AuditoryWorkingMemoryState,
            self.get_parameter('wm_state_topic').get_parameter_value().string_value,
            self.state_cb,
            10,
        )
        self.get_logger().info(
            f'Auditory memory risk bridge: '
            f"{self.get_parameter('wm_state_topic').value} -> {self.get_parameter('context_topic').value} "
            f'using {self.config_path}')

    def state_cb(self, state: AuditoryWorkingMemoryState) -> None:
        fallback_s = stamp_to_sec(state.header.stamp)
        relevant_episodes = [
            episode for episode in state.active_episodes
            if is_risk_relevant(
                episode,
                float(self.get_parameter('min_episode_novelty').value),
                float(self.get_parameter('max_location_congruence').value),
                float(self.get_parameter('min_arousal_contribution').value),
            )
        ]
        unpublished_episodes = [
            episode for episode in relevant_episodes
            if episode_context_key(episode, fallback_s) not in self.published_context_keys
        ]
        if not unpublished_episodes and not bool(self.get_parameter('publish_empty_context').value):
            return
        self.context_pub.publish(build_audio_context(state, unpublished_episodes, self.config))
        for episode in unpublished_episodes:
            self.published_context_keys.add(episode_context_key(episode, fallback_s))


def main(args=None):
    rclpy.init(args=args)
    node = AuditoryMemoryRiskBridge()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
