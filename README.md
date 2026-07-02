# Auditory Memory System

ROS 2 packages for contextual auditory memory in a social robot.

The system does not classify raw audio. It receives pre-processed
`AuditoryObservation` messages from an upstream audio recognition pipeline and
adds meaning through context, location, temporal regularity, and accumulated
experience.

## Packages

- `auditory_memory_msgs`: ROS 2 message definitions.
- `auditory_memory_core`: working memory, long-term memory, simulator, and rqt
  visualization plugin.
- `auditory_memory_bringup`: launch/bringup package placeholder.

## Main Topics

- `/sound_observation`: input `AuditoryObservation` messages.
- `/auditory_memory/wm_state`: live `AuditoryWorkingMemoryState` from Working
  Memory.
- `/auditory_memory/graph_viz`: JSON graph visualization payload as
  `std_msgs/String`.
- `/auditory_memory/consolidation`: consolidated `AuditoryEpisode` messages from
  Working Memory to Long-Term Memory.

## Build

From the workspace root:

```bash
cd /home/lab/auditory_ws
colcon build --symlink-install
source install/setup.bash
```

## Launch Everything

Recommended launch command:

```bash
cd /home/lab/auditory_ws
source install/setup.bash
ros2 launch auditory_memory_bringup auditory_memory.launch.py
```

This starts:

- `long_term_memory_node`
- `working_memory_node`
- `rqt_gui` directly in standalone mode with `AuditoryMemoryPlugin` loaded

You do not need to add the rqt plugin manually from the menu.

To launch the memory nodes without rqt:

```bash
ros2 launch auditory_memory_bringup auditory_memory.launch.py start_rqt:=false
```

To use a custom Long-Term Memory JSON file:

```bash
ros2 launch auditory_memory_bringup auditory_memory.launch.py \
  ltm_path:=/home/lab/auditory_ws/auditory_memory_data/test_ltm.json
```

The simulator is separate. Run it in another terminal. The default mode is a
natural-paced home-day demo that lasts about 15 real minutes at
`speed_multiplier:=1.0`:

```bash
cd /home/lab/auditory_ws
source install/setup.bash
ros2 run auditory_memory_core auditory_day_simulator
```

Natural live demo:

```bash
ros2 run auditory_memory_core auditory_day_simulator --ros-args \
  -p demo_mode:=natural \
  -p speed_multiplier:=1.0
```

Faster demo:

```bash
ros2 run auditory_memory_core auditory_day_simulator --ros-args \
  -p demo_mode:=natural \
  -p speed_multiplier:=5.0
```

Anomaly-focused demo:

```bash
ros2 run auditory_memory_core auditory_day_simulator --ros-args \
  -p demo_mode:=anomaly \
  -p speed_multiplier:=1.0
```

Multi-day learning demo:

```bash
ros2 run auditory_memory_core auditory_day_simulator --ros-args \
  -p demo_mode:=learning \
  -p num_days:=3 \
  -p speed_multiplier:=3.0
```

Manual launch is also possible. Use separate terminals and source the workspace
in each one.

Terminal 1, Long-Term Memory:

```bash
cd /home/lab/auditory_ws
source install/setup.bash
ros2 run auditory_memory_core long_term_memory_node
```

Terminal 2, Working Memory:

```bash
cd /home/lab/auditory_ws
source install/setup.bash
ros2 run auditory_memory_core working_memory_node
```

Terminal 3, rqt viewer with the plugin loaded:

```bash
cd /home/lab/auditory_ws
source install/setup.bash
rqt --standalone auditory_memory_core.auditory_memory_plugin.AuditoryMemoryPlugin
```

Terminal 4, full-day simulator:

```bash
cd /home/lab/auditory_ws
source install/setup.bash
ros2 run auditory_memory_core auditory_day_simulator
```

## Recommended LTM Storage

The Long-Term Memory graph is stored as human-readable JSON. The path is
configured with the `ltm_path` parameter.

Default:

```text
/tmp/auditory_ltm.json
```

For real robot or experiment runs, prefer a path outside `src/`:

```text
/home/lab/auditory_ws/auditory_memory_data/ltm.json
```

Reason: `src/auditory_memory_system/` is source code and is a Git repository.
Robot memory changes continuously, so storing it in `src/` can pollute
`git status` and risks accidentally committing robot-specific/private memory.

Run both memory nodes with the same `ltm_path`:

```bash
ros2 run auditory_memory_core long_term_memory_node --ros-args \
  -p ltm_path:=/home/lab/auditory_ws/auditory_memory_data/ltm.json
```

```bash
ros2 run auditory_memory_core working_memory_node --ros-args \
  -p ltm_path:=/home/lab/auditory_ws/auditory_memory_data/ltm.json
```

## Working Memory

Working Memory is short-term and volatile. It is implemented as a NetworkX
directed graph in RAM.

It stores recent auditory context:

- active sound episodes
- sound type nodes
- location nodes
- episode nodes
- recent sound-sound co-occurrence
- recent sound-location associations
- activation levels
- focused sound/location
- global arousal level

Working Memory is active, not passive storage. It continuously updates node
activation, edge weights, focus, arousal, and consolidation readiness.

### Timestamp Semantics

Working Memory uses `AuditoryObservation.header.stamp` as the observation time
when it is present. This is important for simulator demos: a sound at simulated
`19:45` is treated as 15 simulated minutes after a sound at simulated `19:30`,
even if both messages arrive only seconds apart in real time.

The observation timestamp is used for:

- time-of-day expectedness in Long-Term Memory novelty evaluation
- episode `started_at` and `last_heard`
- sound co-occurrence windows
- contextual urgency windows

If an observation has an empty or zero timestamp, Working Memory falls back to
wall-clock time. Consolidation checks and episode cleanup use a logical clock
advanced to the latest observation timestamp or current wall time, whichever is
later. Visual decay of activation and arousal uses wall-clock timer intervals so
arousal spikes remain visible in live rqt even when simulated timestamps jump by
many minutes between events. Long-Term Memory edge maintenance metadata such as
`last_updated` uses wall-clock time for persistence/pruning bookkeeping, not for
novelty, co-occurrence, or contextual urgency decisions.

When an episode has not been heard for longer than `inactive_gap_s`, it becomes
ready for consolidation. Working Memory publishes it on
`/auditory_memory/consolidation` and also updates its local LTM model so novelty
can adapt immediately during the same run.

Old consolidated episodes disappear from Working Memory after `episode_ttl_s`.

## Long-Term Memory

Long-Term Memory is persistent and cross-session. It is also a NetworkX directed
graph, serialized to JSON.

It learns from consolidated episodes and stores:

- sound familiarity
- how often a sound has been heard
- where sounds are usually heard
- location sound profiles
- sound-sound co-occurrence patterns
- approximate time-of-day patterns
- edge weights between sounds and locations

Example learned patterns:

```text
sound:alarm -> location:bedroom
location:bedroom -> sound:alarm
sound:coffee_machine -> location:kitchen
location:kitchen -> sound:coffee_machine
```

Repeated normal events become familiar. Rare or contextually wrong events remain
novel.

The `long_term_memory_node` is responsible for periodically saving the JSON file
and saving again on clean shutdown.

## Novelty

Novelty means how unexpected a sound is in its current context.

It is computed from three factors:

- sound familiarity: has this sound been heard often before?
- location-sound congruence: is this sound expected in this room?
- time-of-day expectedness: does this sound usually happen around this time?

Approximate formula used by the current implementation:

```text
novelty =
  0.40 * (1.0 - familiarity)
+ 0.45 * (1.0 - location_congruence)
+ 0.15 * (1.0 - time_expectedness)
```

Examples:

- `alarm` in `bedroom` at 07:00 becomes low novelty after repetition.
- `alarm` in `bedroom` at 15:00 is more novel because the time is unexpected.
- `water_running` in `bathroom` should become routine.
- `water_running` in `living_room` stays highly novel because the location is
  incongruent.
- `glass_breaking` in `kitchen` stays highly novel because it is rare.

## Arousal

Arousal is the global alertness level of the auditory memory system.

Range:

```text
0.0 = calm/background
1.0 = highly alert
```

Arousal increases when high-novelty or location-incongruent observations arrive.
It decays over time when no important sound continues.

Working Memory also computes short-term contextual urgency. When a high-novelty
sound occurs, later sounds in the same room can receive an urgency boost for a
limited simulated-time window. This does not change the base novelty value from
Long-Term Memory; it only increases arousal evidence and focus priority while
the recent context is active.

The Working Memory node logs the components used for arousal and focus, for
example:

```text
Arousal evidence for voices in kitchen: novelty=0.42, contextual_urgency=0.80, contribution=0.62
Focus selected: voices in kitchen | novelty=0.42 | incongruence=0.35 | contextual_urgency=0.80 | score=0.67
```

Default contextual urgency parameters:

- `context_urgency_enabled`: `true`
- `context_urgency_window_s`: `1200.0`
- `context_urgency_min_delay_s`: `1.0`
- `context_urgency_novelty_threshold`: `0.70`
- `context_urgency_same_location_only`: `true`
- `context_urgency_boost`: `0.25`
- `context_urgency_focus_weight`: `0.25`

The mechanism is generic. It does not use simulator labels such as `category`,
`novelty_label`, or `arousal_hint`, and it does not hardcode sound names like
`glass_breaking` or `voices`.

Examples:

- `coffee_machine` in `kitchen` in the morning should eventually produce low
  arousal.
- `voices` from a TV in `living_room` should become less relevant after the LTM
  learns the pattern.
- `glass_breaking` should spike arousal.
- `footsteps + door_opening` at 03:00 should produce a maximum arousal spike.
- `voices` in the kitchen after a recent high-novelty kitchen event should be
  treated as more urgent than the same base sound in routine context.

## Focused Sound

The focused sound is the current foreground auditory event. It is selected from
active episodes using:

- novelty
- location incongruence
- intensity

If `tv_on`, `voices`, and `glass_breaking` are all present, the focused sound
should move to `glass_breaking` because it is the most unusual and urgent event.

## Graph Visualization JSON

The Working Memory node publishes graph visualization data on
`/auditory_memory/graph_viz` as `std_msgs/String` containing JSON:

```json
{
  "nodes": [
    {
      "id": "string",
      "type": "sound_type | location | episode",
      "activation": 0.0,
      "hit_count": 0,
      "is_focused": false,
      "contextual_urgency": 0.0
    }
  ],
  "edges": [
    {
      "source": "string",
      "target": "string",
      "weight": 0.0,
      "relation_type": "co_occurs | heard_in | typical_for | precedes"
    }
  ],
  "arousal": 0.0,
  "focused_sound": "string",
  "focused_location": "string",
  "recent_high_novelty_context": []
}
```

## rqt Graph Viewer

The rqt plugin is called `AuditoryMemoryPlugin` and appears as:

```text
Plugins -> Robot Tools -> Auditory Memory Graph Viewer
```

It subscribes to:

- `/auditory_memory/graph_viz`
- `/auditory_memory/wm_state`

### Node Encoding

- Blue circle: `sound_type` node, for example `alarm`, `voices`,
  `glass_breaking`.
- Green square: `location` node, for example `kitchen`, `bedroom`,
  `living_room`.
- Gray small circle: `episode` node, a concrete sound occurrence at a specific
  time and place.
- Larger node: higher activation.
- More transparent node: lower activation, fading from Working Memory.
- Red border: focused/currently most relevant node.

### Edge Encoding

- Thicker arrow: stronger edge weight.
- Orange arrow: `co_occurs`, two sounds occurred close together.
- Purple arrow: `heard_in`, a sound was heard in a location.
- Green arrow: `typical_for`, a location has learned that a sound is typical.
- Red arrow: `precedes`, one sound tends to happen before another. This relation
  is reserved by the schema; the current implementation mainly uses
  `co_occurs`, `heard_in`, and `typical_for`.

### Side Panel

The side panel shows:

- arousal progress bar
- numeric arousal value
- focused sound
- focused location
- active episodes
- novelty per episode
- contextual urgency per episode
- arousal contribution per episode
- co-occurring sounds
- consolidation readiness
- recent consolidations published on `/auditory_memory/consolidation`
- arousal history over the last 60 seconds

Arousal colors:

- green: `0.0-0.3`, calm/background
- yellow: `0.3-0.6`, moderately relevant
- red: `0.6-1.0`, high alert/anomaly

The `Recent Consolidations` panel lists the last 10 episodes that moved from
Working Memory toward Long-Term Memory. Each row shows simulated time, location,
sound or co-occurring sounds, and duration when available, for example:

```text
08:05 kitchen: coffee_machine
10:45 living_room: tv_on + voices
17:35 hallway: door_opening + footsteps
```

### Toolbar

- Topic selector: change the graph JSON topic.
- Pause/Resume: freeze or resume display updates.
- Clear: reset local display state.
- Snapshot: save the current graph as a PNG in
  `~/auditory_memory_snapshots`.

## Full-Day Simulator

The simulator node publishes `AuditoryObservation` messages on
`/sound_observation`. It keeps the existing room pose structure and the same
message type while adding paced demo scenarios for live analysis.

Default parameters:

- `demo_mode`: `natural`
- `sim_duration_s`: `0.0`
- `sim_day_hours`: `0.0`
- `publish_topic`: `/sound_observation`
- `num_days`: `3`
- `speed_multiplier`: `1.0`

`sim_duration_s:=0.0` uses the selected mode default. The natural mode default
is about 15 real minutes before applying `speed_multiplier`. Higher speed
multipliers such as `2.0`, `5.0`, or `10.0` accelerate the same scenario.

Run default natural simulation:

```bash
ros2 run auditory_memory_core auditory_day_simulator
```

Run natural mode explicitly:

```bash
ros2 run auditory_memory_core auditory_day_simulator --ros-args \
  -p demo_mode:=natural \
  -p speed_multiplier:=1.0
```

Run the same day faster:

```bash
ros2 run auditory_memory_core auditory_day_simulator --ros-args \
  -p demo_mode:=natural \
  -p speed_multiplier:=5.0
```

Run the built-in fast mode:

```bash
ros2 run auditory_memory_core auditory_day_simulator --ros-args \
  -p demo_mode:=fast
```

Run a short anomaly-focused scenario:

```bash
ros2 run auditory_memory_core auditory_day_simulator --ros-args \
  -p demo_mode:=anomaly \
  -p speed_multiplier:=1.0
```

Run a multi-day learning scenario:

```bash
ros2 run auditory_memory_core auditory_day_simulator --ros-args \
  -p demo_mode:=learning \
  -p num_days:=3 \
  -p speed_multiplier:=3.0
```

The simulator logs events like:

```text
[SIM D1 08:05] KITCHEN | coffee_machine | ROUTINE | expected novelty: MEDIUM | arousal hint: 0.45 | Morning coffee routine
[SIM D1 19:30] KITCHEN | glass_breaking | ALARMING | expected novelty: MAX | arousal hint: 0.98 | Rare alarming sound in kitchen
```

At startup it also logs the selected mode, simulated duration, real duration,
and speed multiplier.

Demo modes:

- `natural`: one realistic home day from morning to night, paced for rqt.
- `fast`: the same home day compressed for quick testing.
- `anomaly`: a short scenario centered on unusual or alarming night events.
- `learning`: repeated routine days for observing Long-Term Memory familiarity.

Natural home-day events include:

- morning alarm in the bedroom
- voices in the bedroom after waking up
- water running in the bathroom
- coffee machine in the kitchen
- door closing when the person leaves
- TV or voices in the living room
- phone ringing during the day
- door opening and footsteps when the person returns home
- cooking sounds in the kitchen
- evening TV in the living room
- quiet bedroom sounds at night

Unusual, unknown, and alarming events include:

- `glass_breaking` in the kitchen in the evening
- `door_opening` and `footsteps` at 03:00 in anomaly mode
- `alarm` at an unusual time and in an unusual room in anomaly mode
- `unknown_sound`, `metallic_crash`, or `unidentified_noise`

Simulated rooms:

- `kitchen`
- `living_room`
- `bedroom`
- `bathroom`
- `hallway`

The anomaly mode includes:

```text
03:00 hallway: door_opening + footsteps
03:18 living_room: unknown_sound
03:45 kitchen: metallic_crash
04:20 living_room: alarm
```

These events are separated from normal routine events so their novelty,
activation, focus, arousal, and decay are easy to observe.

### Contextual Urgency Demo Check

To verify context-derived urgency with the natural demo:

```bash
ros2 run auditory_memory_core auditory_day_simulator --ros-args \
  -p demo_mode:=natural \
  -p speed_multiplier:=1.0
```

Watch the rqt graph and Working Memory logs:

- `tv_on + voices` in the living room should show low or no contextual urgency.
- `glass_breaking` in the kitchen should produce high base novelty and arousal.
- `glass_breaking` should create an entry in `recent_high_novelty_context` in
  `/auditory_memory/graph_viz`.
- `voices` in the kitchen shortly afterward should keep its own base novelty but
  receive `contextual_urgency` because it follows a recent high-novelty kitchen
  event.
- The Working Memory node should log a message like
  `Context urgency boost: voices in kitchen occurred 900s after high-novelty glass_breaking in kitchen`.
- The Working Memory node should also log arousal evidence showing novelty and
  contextual urgency separately.
- If `voices` becomes focused, the focus log should show novelty, incongruence,
  contextual urgency, and final score.
- Routine `tv_on + voices` in the living room should not receive the same boost
  from the same multi-sound event because of `context_urgency_min_delay_s`.
- In anomaly mode, sounds after the 03:00 high-novelty event should remain
  contextually urgent while they are within `context_urgency_window_s`.
- This urgency is not caused by simulator annotations. The simulator-only fields
  `category`, `novelty_label`, and `arousal_hint` are not published to Working
  Memory.

## Expected Demo Behavior

During the natural and learning demos:

- `alarm -> bedroom` should become a strong familiar edge.
- `coffee_machine -> kitchen` should become a strong morning routine.
- `voices -> living_room` should become less alarming as the TV pattern is
  learned.
- `glass_breaking -> kitchen` should stay rare and novel.
- Routine sounds should gradually become less novel.
- Repeated room-sound associations should strengthen in Long-Term Memory.
- `coffee_machine` should become associated with the kitchen.
- `alarm` should become associated with the bedroom in the morning.
- `glass_breaking` should remain rare and highly novel.
- `door_opening + footsteps` at 03:00 should produce a strong novelty/arousal
  spike in anomaly mode.
- Unknown sounds should appear unfamiliar and contextually unexpected.
- Episode nodes should appear, fade, consolidate, and disappear from Working
  Memory.

## Useful Parameters

Working Memory:

- `observation_topic`
- `state_topic`
- `graph_viz_topic`
- `consolidation_topic`
- `timer_hz`
- `active_gap_s`
- `inactive_gap_s`
- `episode_ttl_s`
- `co_occurrence_window_s`
- `arousal_decay`
- `context_urgency_enabled`
- `context_urgency_window_s`
- `context_urgency_min_delay_s`
- `context_urgency_novelty_threshold`
- `context_urgency_same_location_only`
- `context_urgency_boost`
- `context_urgency_focus_weight`
- `ltm_path`
- `location_config_path`

Long-Term Memory:

- `consolidation_topic`
- `ltm_path`
- `ltm_serialize_interval_s`
- `ltm_prune_min_weight`
- `ltm_prune_older_than_s`

Simulator:

- `demo_mode`
- `sim_duration_s`
- `sim_day_hours`
- `publish_topic`
- `num_days`
- `speed_multiplier`
