# Auditory Memory System

ROS 2 packages for contextual auditory memory in a social robot.

The system does not classify raw audio. It receives pre-processed
`AuditoryObservation` messages from an upstream audio perception pipeline or the
included simulator, then adds Working Memory, Long-Term Memory pattern learning,
novelty, arousal, focus, and rqt visualization.

## Packages

- `auditory_memory_msgs`: ROS 2 message definitions.
- `auditory_memory_core`: Working Memory, Long-Term Memory, simulators, and rqt
  plugin.
- `auditory_memory_bringup`: launch files.

## Build

From the workspace root:

```bash
cd /home/lab/auditory_ws
colcon build --symlink-install
source install/setup.bash
```

## Launch

Launch memory nodes and rqt:

```bash
cd /home/lab/auditory_ws
source install/setup.bash
ros2 launch auditory_memory_bringup auditory_memory.launch.py
```

Launch without rqt:

```bash
ros2 launch auditory_memory_bringup auditory_memory.launch.py start_rqt:=false
```

Use a custom Long-Term Memory file:

```bash
ros2 launch auditory_memory_bringup auditory_memory.launch.py \
  ltm_path:=/home/lab/auditory_ws/auditory_memory_data/ltm.json
```

Run the simulator in another terminal:

```bash
cd /home/lab/auditory_ws
source install/setup.bash
ros2 run auditory_memory_core auditory_day_simulator
```

Run the empty-memory learn-then-anomaly demo:

```bash
rm -f /tmp/auditory_ltm_demo.json
ros2 launch auditory_memory_bringup auditory_memory.launch.py \
  ltm_path:=/tmp/auditory_ltm_demo.json
```

In another terminal:

```bash
ros2 run auditory_memory_core auditory_day_simulator --ros-args \
  -p demo_mode:=learn_then_anomaly \
  -p speed_multiplier:=1.0
```

## Documentation

- [Overview](docs/overview.md)
- [Architecture](docs/architecture.md)
- [Working Memory](docs/working_memory.md)
- [Long-Term Memory](docs/long_term_memory.md)
- [Novelty And Arousal](docs/novelty_arousal.md)
- [Contextual Urgency](docs/contextual_urgency.md)
- [Pattern Learning](docs/pattern_learning.md)
- [Simulator Demos](docs/simulator_demos.md)
- [rqt Plugin](docs/rqt_plugin.md)
- [Topics And Messages](docs/topics_and_messages.md)
- [Timestamp Semantics](docs/timestamp_semantics.md)

## Main Topics

- `/sound_observation`
- `/auditory_memory/wm_state`
- `/auditory_memory/graph_viz`
- `/auditory_memory/consolidation`
- `/auditory_memory/ltm_patterns`

See [Topics And Messages](docs/topics_and_messages.md) for details.
