#!/usr/bin/env python3
import rclpy
from rclpy.node import Node

from auditory_memory_msgs.msg import AuditoryObservation
from geometry_msgs.msg import Pose


class FakeSoundObservationPublisher(Node):
    """
    Publica AuditoryObservation siguiendo un guion temporal para testear:
      - creación NEW
      - continuidad perceptiva (ACTIVE/BACKGROUND según tu lógica)
      - paso a INACTIVE tras inactive_gap_s

    Publica en /sound_observation
    """

    def __init__(self):
        super().__init__('fake_sound_observation_publisher')
        self.pub = self.create_publisher(AuditoryObservation, '/sound_observation', 10)

        # Tick: cada cuánto evaluamos el guion (no tiene por qué ser igual al timer del memory node)
        self.dt = 0.1
        self.t = 0.0

        # Guion: lista de segmentos (start, end, sound_id, description, rate_hz)
        # rate_hz = cuántas observaciones por segundo se publican dentro del segmento
        #
        # Ajusta duraciones para comprobar transiciones:
        # - deja silencios > inactive_gap_s para forzar INACTIVE
        self.script = [
            # 0-3s: "tv" continuo (simula un fondo)
            (0.0, 3.0, "tv", "TV playing", 4.0),

            # 3-4.2s: silencio (gap corto, NO debería llegar a INACTIVE si inactive_gap_s=5)
            (3.0, 4.2, None, None, 0.0),

            # 4.2-4.8s: "scream" burst corto
            (4.2, 4.8, "scream", "A person screams", 6.0),

            # 4.8-10.5s: silencio largo (si inactive_gap_s=5, aquí debería pasar a INACTIVE)
            (4.8, 10.5, None, None, 0.0),

            # 10.5-13.0s: vuelve "tv" (debería crear de nuevo o reactivar según key)
            (10.5, 13.0, "tv", "TV playing again", 4.0),
        ]

        # Control interno por sound_id para espaciar publicaciones según rate_hz
        self._last_pub_time = {}  # sound_id -> last_pub_t

        self.timer = self.create_timer(self.dt, self.tick)
        self.get_logger().info("FakeSoundObservationPublisher running, publishing to /sound_observation")

    def tick(self):
        self.t += self.dt

        seg = self._current_segment(self.t)
        if seg is None:
            # Fin del guion: parar
            self.get_logger().info("Script finished. Stopping publisher node.")
            rclpy.shutdown()
            return

        start, end, sound_id, desc, rate_hz = seg

        if sound_id is None or rate_hz <= 0.0:
            # Segmento de silencio: no publicamos nada
            return

        # Publicar a la cadencia rate_hz dentro del segmento
        period = 1.0 / rate_hz
        last = self._last_pub_time.get(sound_id, None)
        if last is None or (self.t - last) >= period:
            self._last_pub_time[sound_id] = self.t
            self.publish_observation(sound_id, desc)

    def publish_observation(self, sound_id: str, desc: str):
        msg = AuditoryObservation()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "map"

        msg.description = desc
        msg.keywords = [sound_id]

        # Pose fija (ajústala si quieres simular habitaciones)
        msg.pose = Pose()
        msg.pose.position.x = 1.0
        msg.pose.position.y = 2.0
        msg.pose.position.z = 0.0
        msg.pose.orientation.w = 1.0

        self.pub.publish(msg)
        self.get_logger().info(f"Published: {sound_id} ({desc})")

    def _current_segment(self, t: float):
        for seg in self.script:
            start, end, *_ = seg
            if start <= t < end:
                return seg
        return None


def main(args=None):
    rclpy.init(args=args)
    node = FakeSoundObservationPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
