# Simulator Demos

The simulator publishes `AuditoryObservation` messages on `/sound_observation`.
It does not control novelty or arousal directly. Its annotation fields are used
only in logs for explanation.

## Common Parameters

- `demo_mode`: `natural`, `fast`, `anomaly`, `learning`, or
  `learn_then_anomaly`
- `publish_topic`: default `/sound_observation`
- `num_days`: used by learning-style demos
- `speed_multiplier`: speeds up the demo without changing simulated timestamps
- `sim_duration_s`: override real duration when nonzero
- `sim_day_hours`: override simulated span when nonzero

## Natural

One realistic home day from morning to night, paced for rqt.

```bash
ros2 run auditory_memory_core auditory_day_simulator --ros-args \
  -p demo_mode:=natural \
  -p speed_multiplier:=1.0
```

Expected observations include morning alarm, bathroom water, coffee machine,
door sounds, TV/voices, cooking, an alarming glass-breaking event, and evening
routine sounds.

## Fast

The same general home-day scenario compressed for quick testing.

```bash
ros2 run auditory_memory_core auditory_day_simulator --ros-args \
  -p demo_mode:=fast
```

## Anomaly

A short scenario centered on unusual or alarming night events.

```bash
ros2 run auditory_memory_core auditory_day_simulator --ros-args \
  -p demo_mode:=anomaly \
  -p speed_multiplier:=1.0
```

Events include `door_opening + footsteps` at `03:00`, `unknown_sound`,
`metallic_crash`, and an alarm in an unusual room/time.

## Learning

Repeated routine days for observing Long-Term Memory familiarity and pattern
reinforcement.

```bash
ros2 run auditory_memory_core auditory_day_simulator --ros-args \
  -p demo_mode:=learning \
  -p num_days:=3 \
  -p speed_multiplier:=3.0
```

Watch the rqt pattern panel for repeated room-sound associations and
co-occurrence patterns strengthening.

## Learn Then Anomaly

This mode is intended for demos starting from empty Long-Term Memory. It shows:

```text
learn pattern -> observe anomaly -> continue learning -> observe another anomaly
```

Run memory nodes and rqt with an empty LTM file:

```bash
rm -f /tmp/auditory_ltm_demo.json
ros2 launch auditory_memory_bringup auditory_memory.launch.py \
  ltm_path:=/tmp/auditory_ltm_demo.json
```

Run the simulator in another terminal:

```bash
ros2 run auditory_memory_core auditory_day_simulator --ros-args \
  -p demo_mode:=learn_then_anomaly \
  -p speed_multiplier:=1.0
```

At `speed_multiplier:=1.0`, the demo runs in about 15 real minutes. Use
`speed_multiplier:=3.0` or `5.0` for faster testing.

The demo interleaves phases:

- initial routine pattern learning
- first anomaly after initial learning: `water_running` in `living_room`
- return to routine reinforcement
- second anomaly after additional learning: `alarm` in `living_room` at night
- final anomaly moment: `door_opening + footsteps` at `03:00`, `unknown_sound`,
  and `glass_breaking`
- return to routine reinforcement

Watch rqt for:

- `alarm -> bedroom` and `alarm -> morning`
- `coffee_machine -> kitchen` and `coffee_machine -> morning`
- `tv_on <-> voices`
- `door_opening <-> footsteps`
- anomalous events with weaker or violated pattern support and higher
  novelty/arousal/focus

No robot reaction is implemented in this demo.
