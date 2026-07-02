import json
import math
import os
import time
import uuid
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import networkx as nx
from builtin_interfaces.msg import Time


def stamp_to_sec(stamp: Time) -> float:
    return float(stamp.sec) + float(stamp.nanosec) / 1e9


def sec_to_stamp(value: float) -> Time:
    stamp = Time()
    stamp.sec = int(value)
    stamp.nanosec = int((value - int(value)) * 1e9)
    return stamp


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


@dataclass
class NoveltyEvidence:
    familiarity: float
    location_congruence: float
    time_expectedness: float
    novelty: float


@dataclass
class ContextEvent:
    sound_type: str
    location_id: str
    timestamp_s: float
    novelty: float


class LongTermMemory:
    """Persistent graph of learned auditory regularities."""

    def __init__(self, path: str):
        self.path = os.path.expanduser(path)
        self.graph = nx.DiGraph()
        self.load()

    def load(self) -> None:
        if not self.path or not os.path.exists(self.path):
            return
        with open(self.path, 'r', encoding='utf-8') as stream:
            data = json.load(stream)
        self.graph.clear()
        for node in data.get('nodes', []):
            node_id = node.get('id')
            if node_id:
                attrs = {k: v for k, v in node.items() if k != 'id'}
                self.graph.add_node(node_id, **attrs)
        for edge in data.get('edges', []):
            source = edge.get('source')
            target = edge.get('target')
            if source and target:
                attrs = {k: v for k, v in edge.items() if k not in ('source', 'target')}
                self.graph.add_edge(source, target, **attrs)

    def save(self) -> None:
        if not self.path:
            return
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        data = {
            'nodes': [
                {'id': node_id, **attrs}
                for node_id, attrs in sorted(self.graph.nodes(data=True))
            ],
            'edges': [
                {'source': source, 'target': target, **attrs}
                for source, target, attrs in sorted(self.graph.edges(data=True))
            ],
        }
        with open(self.path, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, indent=2, sort_keys=True)

    def sound_node(self, sound_type: str) -> str:
        return f'sound:{sound_type}'

    def location_node(self, location_id: str) -> str:
        return f'location:{location_id}'

    def evaluate(self, sound_type: str, location_id: str, timestamp_s: float) -> NoveltyEvidence:
        sound_node = self.sound_node(sound_type)
        location_node = self.location_node(location_id)
        familiarity = float(self.graph.nodes.get(sound_node, {}).get('familiarity', 0.0))
        congruence = 0.0
        if self.graph.has_edge(location_node, sound_node):
            congruence = float(self.graph[location_node][sound_node].get('weight', 0.0))
        hour = time.localtime(timestamp_s).tm_hour
        hour_hist = self.graph.nodes.get(sound_node, {}).get('hour_hist', [0] * 24)
        if isinstance(hour_hist, list) and len(hour_hist) == 24 and max(hour_hist, default=0) > 0:
            time_expectedness = float(hour_hist[hour]) / float(max(hour_hist))
        else:
            time_expectedness = 0.0
        novelty = (
            0.40 * (1.0 - familiarity) +
            0.45 * (1.0 - congruence) +
            0.15 * (1.0 - time_expectedness)
        )
        return NoveltyEvidence(
            familiarity=clamp(familiarity),
            location_congruence=clamp(congruence),
            time_expectedness=clamp(time_expectedness),
            novelty=clamp(novelty),
        )

    def consolidate_episode(
        self,
        sound_type: str,
        location_id: str,
        started_at_s: float,
        last_heard_s: float,
        co_occurring_sounds: Iterable[str],
        novelty: float,
    ) -> None:
        now_s = time.time()
        sound_node = self.sound_node(sound_type)
        location_node = self.location_node(location_id)
        self._ensure_sound(sound_node, sound_type)
        self._ensure_location(location_node, location_id)

        sound_attrs = self.graph.nodes[sound_node]
        count = int(sound_attrs.get('episode_count', 0)) + 1
        sound_attrs['episode_count'] = count
        sound_attrs['last_seen'] = last_heard_s
        sound_attrs['familiarity'] = clamp(float(sound_attrs.get('familiarity', 0.0)) + 1.0 / (count + 3.0))
        hour_hist = sound_attrs.get('hour_hist', [0] * 24)
        if not isinstance(hour_hist, list) or len(hour_hist) != 24:
            hour_hist = [0] * 24
        hour_hist[time.localtime(started_at_s).tm_hour] += 1
        sound_attrs['hour_hist'] = hour_hist

        self._reinforce_edge(sound_node, location_node, 'heard_in', novelty, now_s)
        self._reinforce_edge(location_node, sound_node, 'typical_for', novelty, now_s)

        for other in co_occurring_sounds:
            if not other or other == sound_type:
                continue
            other_node = self.sound_node(other)
            self._ensure_sound(other_node, other)
            self._reinforce_edge(sound_node, other_node, 'co_occurs', novelty, now_s)
            self._reinforce_edge(other_node, sound_node, 'co_occurs', novelty, now_s)

    def prune(self, min_weight: float, older_than_s: float) -> None:
        now_s = time.time()
        to_remove = []
        for source, target, attrs in self.graph.edges(data=True):
            weight = float(attrs.get('weight', 0.0))
            last_updated = float(attrs.get('last_updated', now_s))
            if weight < min_weight and now_s - last_updated > older_than_s:
                to_remove.append((source, target))
        self.graph.remove_edges_from(to_remove)

    def _ensure_sound(self, node_id: str, sound_type: str) -> None:
        if not self.graph.has_node(node_id):
            self.graph.add_node(
                node_id,
                type='sound_type',
                sound_type=sound_type,
                familiarity=0.0,
                episode_count=0,
                hour_hist=[0] * 24,
            )

    def _ensure_location(self, node_id: str, location_id: str) -> None:
        if not self.graph.has_node(node_id):
            self.graph.add_node(node_id, type='location', location_id=location_id)

    def _reinforce_edge(self, source: str, target: str, relation_type: str, novelty: float, now_s: float) -> None:
        if self.graph.has_edge(source, target):
            attrs = self.graph[source][target]
            old_weight = float(attrs.get('weight', 0.0))
            attrs['weight'] = clamp(old_weight + 0.15 * (1.0 - old_weight))
            attrs['count'] = int(attrs.get('count', 0)) + 1
            attrs['last_updated'] = now_s
            attrs['last_novelty'] = novelty
        else:
            self.graph.add_edge(
                source,
                target,
                relation_type=relation_type,
                weight=0.2,
                count=1,
                first_seen=now_s,
                last_updated=now_s,
                last_novelty=novelty,
            )


class WorkingMemory:
    """Volatile active auditory memory represented as a NetworkX DiGraph."""

    def __init__(self, ltm: LongTermMemory):
        self.graph = nx.DiGraph()
        self.ltm = ltm
        self.arousal_level = 0.0
        self.focused_episode_id = ''
        self.co_occurrence_window_s = 2.0
        self.context_urgency_enabled = True
        self.context_urgency_window_s = 1200.0
        self.context_urgency_min_delay_s = 1.0
        self.context_urgency_novelty_threshold = 0.70
        self.context_urgency_same_location_only = True
        self.context_urgency_boost = 0.25
        self.context_urgency_focus_weight = 0.25
        self.recent_high_novelty_context: List[ContextEvent] = []
        self.last_context_urgency_info: Optional[Dict] = None
        self.last_arousal_evidence_info: Optional[Dict] = None
        self.last_focus_info: Optional[Dict] = None

    def observe(self, sound_type: str, location_id: str, timestamp_s: float) -> str:
        sound_node = self._sound_node(sound_type)
        location_node = self._location_node(location_id)
        episode_id = self._find_active_episode(sound_type, location_id)
        evidence = self.ltm.evaluate(sound_type, location_id, timestamp_s)
        contextual_urgency, context_source = self._contextual_urgency(sound_type, location_id, timestamp_s)
        arousal_evidence = clamp(evidence.novelty + self.context_urgency_boost * contextual_urgency)

        self._ensure_sound(sound_node, sound_type, timestamp_s)
        self._ensure_location(location_node, location_id, timestamp_s)
        if episode_id is None:
            episode_id = self._episode_node(sound_type, location_id)
            self.graph.add_node(
                episode_id,
                type='episode',
                sound_type=sound_type,
                location_id=location_id,
                timestamp=timestamp_s,
                started_at=timestamp_s,
                last_heard=timestamp_s,
                co_occurring_sounds=[],
                intensity=1.0,
                novelty=evidence.novelty,
                location_congruence=evidence.location_congruence,
                contextual_urgency=contextual_urgency,
                arousal_contribution=arousal_evidence,
                consolidation_ready=False,
                consolidated=False,
            )
            self.graph.add_edge(episode_id, sound_node, relation_type='episode_sound', weight=1.0)
            self.graph.add_edge(episode_id, location_node, relation_type='episode_location', weight=1.0)
        else:
            attrs = self.graph.nodes[episode_id]
            attrs['last_heard'] = timestamp_s
            attrs['intensity'] = clamp(float(attrs.get('intensity', 0.0)) + 0.1)
            attrs['novelty'] = max(float(attrs.get('novelty', 0.0)), evidence.novelty)
            attrs['location_congruence'] = evidence.location_congruence
            attrs['contextual_urgency'] = max(float(attrs.get('contextual_urgency', 0.0)), contextual_urgency)
            attrs['arousal_contribution'] = max(float(attrs.get('arousal_contribution', 0.0)), arousal_evidence)

        sound_attrs = self.graph.nodes[sound_node]
        sound_attrs['activation'] = 1.0
        sound_attrs['hit_count'] = int(sound_attrs.get('hit_count', 0)) + 1
        location_attrs = self.graph.nodes[location_node]
        location_attrs['activation'] = 1.0
        location_attrs['last_active'] = timestamp_s

        self._reinforce_edge(sound_node, location_node, 'heard_in')
        self._reinforce_edge(location_node, sound_node, 'typical_for')
        self._update_co_occurrences(episode_id, sound_type, timestamp_s)
        self.arousal_level = clamp(self.arousal_level + 0.35 * arousal_evidence)
        self.last_arousal_evidence_info = {
            'sound_type': sound_type,
            'location_id': location_id,
            'novelty': evidence.novelty,
            'contextual_urgency': contextual_urgency,
            'contribution': arousal_evidence,
        }
        self._remember_high_novelty_context(sound_type, location_id, timestamp_s, evidence.novelty)
        self.last_context_urgency_info = None
        if contextual_urgency > 0.0 and context_source is not None:
            self.last_context_urgency_info = {
                'sound_type': sound_type,
                'location_id': location_id,
                'contextual_urgency': contextual_urgency,
                'elapsed_s': max(0.0, timestamp_s - context_source.timestamp_s),
                'source_sound_type': context_source.sound_type,
                'source_location_id': context_source.location_id,
                'source_novelty': context_source.novelty,
            }
        self._update_focus()
        return episode_id

    def update(self, now_s: float, dt_s: float, arousal_decay: float, inactive_gap_s: float) -> List[str]:
        decay_factor = math.exp(-max(0.0, dt_s) * 0.25)
        for node_id, attrs in self.graph.nodes(data=True):
            if attrs.get('type') in ('sound_type', 'location'):
                attrs['activation'] = clamp(float(attrs.get('activation', 0.0)) * decay_factor)
        for source, target, attrs in self.graph.edges(data=True):
            if attrs.get('relation_type') == 'co_occurs':
                attrs['weight'] = clamp(float(attrs.get('weight', 0.0)) * math.exp(-dt_s * 0.05))
        ready = []
        for node_id, attrs in self._episode_nodes():
            if attrs.get('consolidated'):
                continue
            if now_s - float(attrs.get('last_heard', now_s)) > inactive_gap_s:
                attrs['consolidation_ready'] = True
                ready.append(node_id)
        self.arousal_level = clamp(self.arousal_level * math.exp(-max(0.0, dt_s) * arousal_decay))
        self._update_focus()
        return ready

    def forget_old_episodes(self, now_s: float, episode_ttl_s: float) -> None:
        to_remove = []
        for node_id, attrs in self._episode_nodes():
            if attrs.get('consolidated') and now_s - float(attrs.get('last_heard', now_s)) > episode_ttl_s:
                to_remove.append(node_id)
        self.graph.remove_nodes_from(to_remove)

    def mark_consolidated(self, episode_id: str) -> None:
        if self.graph.has_node(episode_id):
            self.graph.nodes[episode_id]['consolidated'] = True

    def active_episode_ids(self) -> List[str]:
        return [
            node_id for node_id, attrs in self._episode_nodes()
            if not attrs.get('consolidated')
        ]

    def episode_attrs(self, episode_id: str) -> Dict:
        return self.graph.nodes[episode_id]

    def graph_viz(self) -> Dict:
        return {
            'nodes': [
                {
                    'id': node_id,
                    'type': attrs.get('type', ''),
                    'activation': float(attrs.get('activation', 0.0)),
                    'hit_count': int(attrs.get('hit_count', 0)),
                    'is_focused': node_id == self.focused_episode_id,
                    'contextual_urgency': float(attrs.get('contextual_urgency', 0.0)),
                }
                for node_id, attrs in self.graph.nodes(data=True)
            ],
            'edges': [
                {
                    'source': source,
                    'target': target,
                    'weight': float(attrs.get('weight', 0.0)),
                    'relation_type': attrs.get('relation_type', ''),
                }
                for source, target, attrs in self.graph.edges(data=True)
            ],
            'arousal': self.arousal_level,
            'focused_sound': self.focused_sound_location()[0],
            'focused_location': self.focused_sound_location()[1],
            'recent_high_novelty_context': [
                {
                    'sound_type': item.sound_type,
                    'location_id': item.location_id,
                    'timestamp_s': item.timestamp_s,
                    'novelty': item.novelty,
                }
                for item in self.recent_high_novelty_context
            ],
        }

    def focused_sound_location(self) -> Tuple[str, str]:
        if not self.focused_episode_id or not self.graph.has_node(self.focused_episode_id):
            return '', ''
        attrs = self.graph.nodes[self.focused_episode_id]
        return attrs.get('sound_type', ''), attrs.get('location_id', '')

    def _ensure_sound(self, node_id: str, sound_type: str, timestamp_s: float) -> None:
        if not self.graph.has_node(node_id):
            self.graph.add_node(
                node_id,
                type='sound_type',
                sound_type=sound_type,
                activation=0.0,
                hit_count=0,
                first_seen=timestamp_s,
                is_focused=False,
            )

    def _ensure_location(self, node_id: str, location_id: str, timestamp_s: float) -> None:
        if not self.graph.has_node(node_id):
            self.graph.add_node(
                node_id,
                type='location',
                location_id=location_id,
                activation=0.0,
                last_active=timestamp_s,
            )

    def _reinforce_edge(self, source: str, target: str, relation_type: str) -> None:
        if self.graph.has_edge(source, target):
            attrs = self.graph[source][target]
            attrs['weight'] = clamp(float(attrs.get('weight', 0.0)) + 0.1)
        else:
            self.graph.add_edge(source, target, relation_type=relation_type, weight=0.1)

    def _update_co_occurrences(self, episode_id: str, sound_type: str, timestamp_s: float) -> None:
        co_occurring = []
        for other_id, attrs in self._episode_nodes():
            if other_id == episode_id or attrs.get('consolidated'):
                continue
            if abs(timestamp_s - float(attrs.get('last_heard', 0.0))) <= self.co_occurrence_window_s:
                other_sound = attrs.get('sound_type', '')
                co_occurring.append(other_sound)
                self._reinforce_edge(self._sound_node(sound_type), self._sound_node(other_sound), 'co_occurs')
                self._reinforce_edge(self._sound_node(other_sound), self._sound_node(sound_type), 'co_occurs')
        self.graph.nodes[episode_id]['co_occurring_sounds'] = sorted(set(co_occurring))

    def _contextual_urgency(
        self,
        sound_type: str,
        location_id: str,
        timestamp_s: float,
    ) -> Tuple[float, Optional[ContextEvent]]:
        if not self.context_urgency_enabled:
            return 0.0, None
        self._prune_high_novelty_context(timestamp_s)
        best_urgency = 0.0
        best_event = None
        for event in self.recent_high_novelty_context:
            if event.sound_type == sound_type and event.location_id == location_id:
                continue
            if self.context_urgency_same_location_only and event.location_id != location_id:
                continue
            elapsed_s = timestamp_s - event.timestamp_s
            if elapsed_s < self.context_urgency_min_delay_s or elapsed_s > self.context_urgency_window_s:
                continue
            recency = 1.0 - (elapsed_s / max(1.0, self.context_urgency_window_s))
            novelty_strength = clamp(
                (event.novelty - self.context_urgency_novelty_threshold) /
                max(0.01, 1.0 - self.context_urgency_novelty_threshold))
            urgency = clamp(max(recency, 0.25) * novelty_strength)
            if urgency > best_urgency:
                best_urgency = urgency
                best_event = event
        return best_urgency, best_event

    def _remember_high_novelty_context(
        self,
        sound_type: str,
        location_id: str,
        timestamp_s: float,
        novelty: float,
    ) -> None:
        if not self.context_urgency_enabled:
            return
        self._prune_high_novelty_context(timestamp_s)
        if novelty < self.context_urgency_novelty_threshold:
            return
        self.recent_high_novelty_context.append(ContextEvent(sound_type, location_id, timestamp_s, novelty))

    def _prune_high_novelty_context(self, timestamp_s: float) -> None:
        window_s = max(0.0, self.context_urgency_window_s)
        self.recent_high_novelty_context = [
            event for event in self.recent_high_novelty_context
            if 0.0 <= timestamp_s - event.timestamp_s <= window_s
        ]

    def _update_focus(self) -> None:
        previous_focused_episode_id = self.focused_episode_id
        best_id = ''
        best_score = 0.0
        best_components = None
        for node_id, attrs in self._episode_nodes():
            if attrs.get('consolidated'):
                continue
            novelty = float(attrs.get('novelty', 0.0))
            incongruence = 1.0 - float(attrs.get('location_congruence', 0.0))
            intensity = float(attrs.get('intensity', 0.0))
            contextual_urgency = float(attrs.get('contextual_urgency', 0.0))
            score = (
                0.65 * novelty +
                0.25 * incongruence +
                0.10 * intensity +
                self.context_urgency_focus_weight * contextual_urgency
            )
            if score > best_score:
                best_score = score
                best_id = node_id
                best_components = {
                    'sound_type': attrs.get('sound_type', ''),
                    'location_id': attrs.get('location_id', ''),
                    'novelty': novelty,
                    'incongruence': incongruence,
                    'intensity': intensity,
                    'contextual_urgency': contextual_urgency,
                    'score': score,
                }
        self.focused_episode_id = best_id
        for node_id, attrs in self.graph.nodes(data=True):
            attrs['is_focused'] = node_id == best_id
        self.last_focus_info = None
        if best_id and best_id != previous_focused_episode_id:
            self.last_focus_info = best_components

    def _find_active_episode(self, sound_type: str, location_id: str) -> Optional[str]:
        for node_id, attrs in self._episode_nodes():
            if attrs.get('consolidated'):
                continue
            if attrs.get('sound_type') == sound_type and attrs.get('location_id') == location_id:
                return node_id
        return None

    def _episode_nodes(self):
        return [
            (node_id, attrs) for node_id, attrs in self.graph.nodes(data=True)
            if attrs.get('type') == 'episode'
        ]

    def _sound_node(self, sound_type: str) -> str:
        return f'sound:{sound_type}'

    def _location_node(self, location_id: str) -> str:
        return f'location:{location_id}'

    def _episode_node(self, sound_type: str, location_id: str) -> str:
        return f'episode:{sound_type}:{location_id}:{uuid.uuid4().hex[:8]}'
