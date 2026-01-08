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

            self.declare_parameter('timer_hz', 5.0)
            self.declare_parameter('active_gap_s', 1.0)    
            self.declare_parameter('inactive_gap_s', 5.0)   # si no se oye en > 5s: INACTIVE
            self.declare_parameter('min_active_duration_s', 0.5) # duración mínima para considerar ACTIVE
            self.declare_parameter('forget_s', 60.0) # tiempo que lleva inactivo para olvidarlo

            self.declare_parameter('relevance_threshold', 0.6) #decidir si es relevante o no: ACTIVE / BACKGROUND
            self.declare_parameter('w_conf', 0.6) # si el modelo está seguro de la clasificación sube la relevancia
            self.declare_parameter('w_freq', 0.2) # reforzar si se oye frecuentemente
            self.declare_parameter('w_dur', 0.2) # peso de la duracion del evento

            self.declare_parameter('dur_ref_s', 2.0) # persistente
            self.declare_parameter('hits_max', 10) # maximo esperado de hits en la ventana reciente
            self.declare_parameter('recent_window_s', 120.0) # ventana de tiempo para calcular frecuencia

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

            timer_hz = float(self.get_parameter('timer_hz').value)
            self._timer_period = 1.0 / max(timer_hz, 0.1)
            self._last_timer_sec = None
            self.timer_ = self.create_timer(self._timer_period, self.timer_cb)

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

                obs_sec = self.stamp_to_sec(msg.header.stamp)
                entry.recent_hits.append(obs_sec)

                self.memory[key] = entry
            else:
                entry = self.memory[key]
                entry.auditory_object.header = msg.header
                entry.auditory_object.last_heard = msg.header.stamp
                if entry.auditory_object.state == AuditoryObject.STATE_INACTIVE:
                    entry.auditory_object.current_event_duration = 0.0
                
                # entry.auditory_object.state = AuditoryObject.STATE_ACTIVE
                obs_sec = self.stamp_to_sec(msg.header.stamp)
                entry.recent_hits.append(obs_sec)


            self.get_logger().info(f'I heard: "{msg.description}" -> ({sound_id}, {loc_id})')
            # state = AuditoryMemoryState()
            # state.header = msg.header
            # state.auditory_objects = [e.auditory_object for e in self.memory.values()]
            # self.pub_.publish(state)

        def stamp_to_sec(self, stamp) -> float:
            return float(stamp.sec) + float(stamp.nanosec) / 1e9
        
        def _remove_old_hits(self, entry, now_sec: float):
            window = float(self.get_parameter('recent_window_s').value)
            self.get_logger().info(f'removing hits older than {window} seconds')
            cutoff = now_sec - window
            self.get_logger().info(f'cutoff time: {cutoff}')
            while entry.recent_hits and entry.recent_hits[0] < cutoff:
                entry.recent_hits.popleft()

        def timer_cb(self):
            now_sec = self.get_clock().now().nanoseconds / 1e9

            if self._last_timer_sec is None:
                self._last_timer_sec = now_sec
                return

            dt = max(0.0, now_sec - self._last_timer_sec) # tiempo desde la última llamada
            self._last_timer_sec = now_sec

            active_gap = float(self.get_parameter('active_gap_s').value)
            inactive_gap = float(self.get_parameter('inactive_gap_s').value)
            forget_s = float(self.get_parameter('forget_s').value)
            min_active = float(self.get_parameter('min_active_duration_s').value)
            
            keys_to_delete = []

            for key, entry in self.memory.items():
                ao = entry.auditory_object
                self.get_logger().info(f'state: {ao.state}')
                self.get_logger().info(f'update despues de {dt}:')
                self.get_logger().info(f'hits: {len(entry.recent_hits)}')
                # 1) Quitar hits antiguos
                self._remove_old_hits(entry, now_sec)
                self.get_logger().info(f'hits: {len(entry.recent_hits)}')
                # 2) gap desde última vez oído
                last_heard_sec = self.stamp_to_sec(ao.last_heard)
                gap = now_sec - last_heard_sec # tiempo desde la última observación
                self.get_logger().info(f'gap: {gap}')
                # 3) Si el sonido se considera "ocurriendo"
                if gap <= active_gap:
                    ao.current_event_duration += dt
                    self.get_logger().info(f'current_event_duration: {ao.current_event_duration}')
                    if ao.state == AuditoryObject.STATE_NEW and ao.current_event_duration >= min_active:
                        ao.state = AuditoryObject.STATE_ACTIVE
                    
                # 4) Si ya no se oye desde hace bastante, pasa a INACTIVE
                if gap > inactive_gap:
                    ao.state = AuditoryObject.STATE_INACTIVE

                # 5) Olvido (limpieza de STM)
                if ao.state == AuditoryObject.STATE_INACTIVE and gap > forget_s:
                    keys_to_delete.append(key)
                self.get_logger().info(f'state: {ao.state}')
            for k in keys_to_delete:
                del self.memory[k]

            # Publicación periódica (opcional pero útil)
            state = AuditoryMemoryState()
            state.header.stamp = self.get_clock().now().to_msg()
            state.header.frame_id = "map"
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
