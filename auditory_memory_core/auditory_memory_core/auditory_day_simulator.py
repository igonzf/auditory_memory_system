from dataclasses import dataclass
from typing import Dict, List, Tuple

import rclpy
from geometry_msgs.msg import Pose
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

from auditory_memory_msgs.msg import AuditoryObservation


@dataclass(frozen=True)
class ScenarioEvent:
    day: int
    hour: int
    minute: int
    room: str
    sounds: Tuple[str, ...]
    category: str
    novelty_label: str
    arousal_hint: float
    description: str


class AuditoryDaySimulator(Node):
    """Publishes paced home-day auditory observations for demos."""

    MODE_REAL_DURATION_S: Dict[str, float] = {
        'natural': 15.0 * 60.0,
        'fast': 3.0 * 60.0,
        'anomaly': 5.0 * 60.0,
        'learning': 5.0 * 60.0,
    }

    ROOM_POSES: Dict[str, Tuple[float, float, float]] = {
        'kitchen': (2.0, 1.0, 0.0),
        'living_room': (5.0, 2.0, 0.0),
        'bedroom': (1.0, 5.0, 0.0),
        'bathroom': (3.5, 5.0, 0.0),
        'hallway': (3.0, 3.0, 0.0),
    }

    def __init__(self):
        super().__init__('auditory_day_simulator')
        self.declare_parameter('demo_mode', 'natural')
        self.declare_parameter('sim_duration_s', 0.0)
        self.declare_parameter('sim_day_hours', 0.0)
        self.declare_parameter('publish_topic', '/sound_observation')
        self.declare_parameter('num_days', 3)
        self.declare_parameter('speed_multiplier', 1.0)

        self.demo_mode = str(self.get_parameter('demo_mode').value).lower()
        if self.demo_mode not in self.MODE_REAL_DURATION_S:
            self.get_logger().warning(
                f'Unknown demo_mode {self.demo_mode!r}; using natural. '
                f'Valid modes: {", ".join(sorted(self.MODE_REAL_DURATION_S))}')
            self.demo_mode = 'natural'
        self.sim_duration_s = float(self.get_parameter('sim_duration_s').value)
        self.sim_day_hours = float(self.get_parameter('sim_day_hours').value)
        self.num_days = int(self.get_parameter('num_days').value)
        self.speed_multiplier = float(self.get_parameter('speed_multiplier').value)
        if self.demo_mode != 'learning':
            self.num_days = 1
        else:
            self.num_days = max(1, self.num_days)

        base_duration_s = self.sim_duration_s
        if base_duration_s <= 0.0:
            base_duration_s = self.MODE_REAL_DURATION_S[self.demo_mode] * self.num_days
        self.real_duration_s = max(1.0, base_duration_s / max(0.01, self.speed_multiplier))

        topic = self.get_parameter('publish_topic').get_parameter_value().string_value
        self.publisher = self.create_publisher(AuditoryObservation, topic, 10)
        self.start_wall_s = self.get_clock().now().nanoseconds / 1e9
        self.time_offset_s = self.start_wall_s
        self.schedule = self._build_schedule()
        self.simulated_start_minute = min(self._event_absolute_minute(event) for event in self.schedule_events)
        self.simulated_end_minute = max(self._event_absolute_minute(event) for event in self.schedule_events)
        self.simulated_duration_hours = max(
            0.0, (self.simulated_end_minute - self.simulated_start_minute) / 60.0)
        self.next_index = 0
        self.finished = False
        self.timer = self.create_timer(0.05, self._tick)
        self.get_logger().info(
            f'Auditory day simulator mode={self.demo_mode} publishing {len(self.schedule)} events to {topic}')
        self.get_logger().info(
            f'Simulated duration: {self.simulated_duration_hours:.1f} h across {self.num_days} day(s); '
            f'real duration: {self.real_duration_s:.1f} s; speed multiplier: {self.speed_multiplier:.2f}')

    def _tick(self):
        if self.finished:
            return
        now_s = self.get_clock().now().nanoseconds / 1e9
        elapsed_s = now_s - self.start_wall_s
        while self.next_index < len(self.schedule) and self.schedule[self.next_index][0] <= elapsed_s:
            _, day_index, event = self.schedule[self.next_index]
            self._publish_event(day_index, event)
            self.next_index += 1
        if self.next_index >= len(self.schedule):
            self.finished = True
            self.get_logger().info('Auditory day simulation complete')
            self.timer.cancel()

    def _build_schedule(self) -> List[Tuple[float, int, ScenarioEvent]]:
        self.schedule_events = self._events_for_mode()
        schedule = []
        start_minute = min(self._event_absolute_minute(event) for event in self.schedule_events)
        end_minute = max(self._event_absolute_minute(event) for event in self.schedule_events)
        simulated_span_minutes = max(1.0, float(end_minute - start_minute))
        if self.sim_day_hours > 0.0:
            simulated_span_minutes = max(simulated_span_minutes, self.sim_day_hours * 60.0)
        for index, event in enumerate(self.schedule_events):
            simulated_offset = self._event_absolute_minute(event) - start_minute
            real_offset = (simulated_offset / simulated_span_minutes) * self.real_duration_s
            schedule.append((real_offset + index * 0.02, event.day - 1, event))
        return sorted(schedule, key=lambda item: item[0])

    def _events_for_mode(self) -> List[ScenarioEvent]:
        if self.demo_mode == 'anomaly':
            return self._anomaly_events()
        if self.demo_mode == 'learning':
            return self._learning_events()
        return self._natural_day_events()

    def _natural_day_events(self, day: int = 1) -> List[ScenarioEvent]:
        return [
            ScenarioEvent(day, 7, 0, 'bedroom', ('alarm',), 'routine', 'MEDIUM', 0.55,
                          'Morning alarm in the bedroom'),
            ScenarioEvent(day, 7, 12, 'bedroom', ('voices',), 'routine', 'LOW', 0.30,
                          'Quiet voices in the bedroom after waking up'),
            ScenarioEvent(day, 7, 35, 'bathroom', ('water_running',), 'routine', 'MEDIUM', 0.42,
                          'Bathroom water running during morning routine'),
            ScenarioEvent(day, 8, 5, 'kitchen', ('coffee_machine',), 'routine', 'MEDIUM', 0.45,
                          'Morning coffee routine'),
            ScenarioEvent(day, 8, 35, 'hallway', ('door_closing',), 'routine', 'LOW', 0.25,
                          'Front door closing when the person leaves'),
            ScenarioEvent(day, 10, 45, 'living_room', ('tv_on', 'voices'), 'routine', 'LOW', 0.24,
                          'Low television voices in the living room'),
            ScenarioEvent(day, 12, 30, 'living_room', ('phone_ringing',), 'routine', 'MEDIUM', 0.50,
                          'Phone ringing during the day'),
            ScenarioEvent(day, 15, 10, 'hallway', ('unidentified_noise',), 'unknown', 'HIGH', 0.78,
                          'Brief unidentified noise in the hallway'),
            ScenarioEvent(day, 17, 35, 'hallway', ('door_opening', 'footsteps'), 'routine', 'MEDIUM', 0.46,
                          'Door opening and footsteps when the person returns home'),
            ScenarioEvent(day, 18, 15, 'kitchen', ('cooking_sounds',), 'routine', 'LOW', 0.32,
                          'Cooking sounds in the kitchen'),
            ScenarioEvent(day, 19, 30, 'kitchen', ('glass_breaking',), 'alarming', 'MAX', 0.98,
                          'Rare alarming sound in kitchen'),
            ScenarioEvent(day, 19, 45, 'kitchen', ('voices',), 'unusual', 'HIGH', 0.72,
                          'Urgent voices after the glass breaking event'),
            ScenarioEvent(day, 20, 35, 'living_room', ('tv_on', 'voices'), 'routine', 'LOW', 0.22,
                          'Evening TV and voices in the living room'),
            ScenarioEvent(day, 22, 15, 'bedroom', ('quiet_bedroom_sounds',), 'routine', 'LOW', 0.12,
                          'Quiet bedroom sounds at night'),
        ]

    def _anomaly_events(self) -> List[ScenarioEvent]:
        return [
            ScenarioEvent(1, 2, 45, 'bedroom', ('quiet_bedroom_sounds',), 'routine', 'LOW', 0.10,
                          'Quiet bedroom baseline before the anomaly'),
            ScenarioEvent(1, 3, 0, 'hallway', ('door_opening', 'footsteps'), 'alarming', 'MAX', 1.0,
                          'Door opening and footsteps at 03:00'),
            ScenarioEvent(1, 3, 18, 'living_room', ('unknown_sound',), 'unknown', 'MAX', 0.95,
                          'Unknown sound after unexpected movement'),
            ScenarioEvent(1, 3, 45, 'kitchen', ('metallic_crash',), 'alarming', 'MAX', 0.98,
                          'Metallic crash from the kitchen at night'),
            ScenarioEvent(1, 4, 20, 'living_room', ('alarm',), 'unusual', 'HIGH', 0.88,
                          'Alarm at an unusual time and in an unusual room'),
        ]

    def _learning_events(self) -> List[ScenarioEvent]:
        events: List[ScenarioEvent] = []
        for day in range(1, self.num_days + 1):
            events.extend(self._routine_learning_day(day))
        return events

    def _routine_learning_day(self, day: int) -> List[ScenarioEvent]:
        return [
            event for event in self._natural_day_events(day)
            if event.category == 'routine'
        ]

    def _publish_event(self, day_index: int, event: ScenarioEvent):
        sim_stamp_s = self.time_offset_s + self._event_absolute_minute(event) * 60
        for sound_index, sound in enumerate(event.sounds):
            msg = AuditoryObservation()
            msg.header.stamp.sec = int(sim_stamp_s)
            msg.header.stamp.nanosec = int(sound_index * 1e7)
            msg.header.frame_id = event.room
            msg.description = event.description
            msg.keywords = [sound, event.room, self._period_keyword(event.hour)]
            msg.pose = self._pose_for_room(event.room)
            self.publisher.publish(msg)
        sounds = '+'.join(event.sounds) if event.sounds else 'silence'
        self.get_logger().info(
            f'[SIM D{day_index + 1} {event.hour:02d}:{event.minute:02d}] '
            f'{event.room.upper()} | {sounds} | {event.category.upper()} | '
            f'expected novelty: {event.novelty_label} | arousal hint: {event.arousal_hint:.2f} | '
            f'{event.description}')

    def _event_absolute_minute(self, event: ScenarioEvent) -> int:
        return (event.day - 1) * 24 * 60 + event.hour * 60 + event.minute

    def _pose_for_room(self, room: str) -> Pose:
        x, y, z = self.ROOM_POSES[room]
        pose = Pose()
        pose.position.x = x
        pose.position.y = y
        pose.position.z = z
        pose.orientation.w = 1.0
        return pose

    def _period_keyword(self, hour: int) -> str:
        if 5 <= hour < 12:
            return 'morning'
        if 12 <= hour < 17:
            return 'afternoon'
        if 17 <= hour < 22:
            return 'evening'
        return 'night'


def main(args=None):
    rclpy.init(args=args)
    node = AuditoryDaySimulator()
    try:
        while rclpy.ok() and not node.finished:
            rclpy.spin_once(node, timeout_sec=0.1)
    except ExternalShutdownException:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
