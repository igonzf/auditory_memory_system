import rclpy
from rclpy.node import Node
from typing import Dict, Tuple
from auditory_memory_msgs.msg import AuditoryObservation, AuditoryObject, AuditoryMemoryState
from auditory_memory_core.memory import MemoryEntry


class AuditoryMemoryNode(Node):
        def __init__(self):
            super().__init__('auditory_memory_node')

            self.declare_parameter('state_topic', '/auditory_memory/state')
            self.declare_parameter('observation_topic', '/sound_observation')

            obs_topic = self.get_parameter('observation_topic').get_parameter_value().string_value
            state_topic = self.get_parameter('state_topic').get_parameter_value().string_value

            self.observation_sub_ = self.create_subscription(
                AuditoryObservation,
                obs_topic,
                self.sound_observation_cb,
                10)
            
            self.pub_ = self.create_publisher(AuditoryMemoryState, state_topic, 10)

            # key: (sound_id, location_id) -> AuditoryObject
            self.memory: Dict[Tuple[str, str], MemoryEntry] = {} # Dict[Tuple[str,str], MemoryEntry]

        def _build_location_id(self, msg: AuditoryObservation) -> str:
            # coger del yaml los limites de cada habitacion en el mapa y comprobar con la pose donde esta
            return f""
        
        def _build_sound_id(self, msg: AuditoryObservation) -> str:
            sound_id = "unknown"

            if msg.keywords:
                sound_id = msg.keywords[0].strip().lower()
            elif msg.description:
                sound_id = msg.description.strip().lower()[:32]
            
            return sound_id

        def sound_observation_cb(self, msg: AuditoryObservation):
            loc_id = self._build_location_id(msg)
            sound_id = self._build_sound_id(msg)
            key = (sound_id, loc_id)

            now = msg.header.stamp
            if key not in self.memory:
                ao = AuditoryObject()
                ao.header = msg.header
                ao.auditory_object_id = sound_id
                ao.location_id = loc_id
                ao.state = AuditoryObject.STATE_NEW
                ao.confidence = 0.8
                ao.novelty = 1.0      
                ao.relevance = 0.5    
                ao.current_event_duration = 0.0
                ao.last_heard = now

                entry = MemoryEntry(
                    auditory_object=ao,
                    episode_start_time=msg.header.stamp
                )

                self.memory[key] = entry
            else:
                entry = self.memory[key]
                entry.header = msg.header
                entry.auditory_object.last_heard = msg.header.stamp
                if entry.auditory_object.state == AuditoryObject.STATE_INACTIVE:
                    entry.auditory_object.current_event_duration = 0.0
                
                entry.auditory_object.state = AuditoryObject.STATE_ACTIVE


            self.get_logger().info(f'I heard: "{msg.description}" -> ({sound_id}, {loc_id})')


            state = AuditoryMemoryState()
            state.header = msg.header
            state.auditory_objects = [e.auditory_object for e in self.memory.values()]
            self.pub_.publish(state)

def main(args=None):
    rclpy.init(args=args)

    node = AuditoryMemoryNode()

    rclpy.spin(node)

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
