# Pattern Learning

Pattern learning happens when Working Memory consolidates finished episodes and
Long-Term Memory reinforces persistent patterns.

## Reinforcement

Each consolidated episode can reinforce multiple patterns:

- a sound count and familiarity value
- a sound-location association
- a location-sound typicality relation
- co-occurrence relations with other sounds from the episode
- a time-of-day histogram for the sound

Repeated routine events increase pattern weights/counts and usually reduce later
novelty for matching events.

## Examples

Repeated morning coffee in the kitchen reinforces:

```text
coffee_machine -> kitchen
coffee_machine -> morning
coffee_machine familiarity/count
```

Repeated bedroom alarms reinforce:

```text
alarm -> bedroom
alarm -> morning
```

Repeated evening TV with voices reinforces:

```text
voices -> living_room
tv_on <-> voices
tv_on -> evening
```

Repeated hallway door movement reinforces:

```text
door_opening -> hallway
footsteps -> hallway
door_opening <-> footsteps
```

## Anomalies

Anomalies are not hardcoded. They emerge when an observation has weak or missing
pattern support.

Examples:

- `water_running` in `living_room` violates the learned bathroom association.
- `alarm` in `living_room` at night violates learned bedroom/morning patterns.
- `door_opening <-> footsteps` at `03:00` may match a learned co-occurrence but
  violate learned time-of-day expectations.
- `unknown_sound` has no learned familiarity, location, or time pattern.

The rqt `Long-Term Memory Patterns` panel shows top learned sound-location,
time-of-day, co-occurrence, and recent pattern updates so the demo can show
routine sounds becoming patterns over time.
