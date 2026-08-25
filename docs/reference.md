# ROS Reference

## Nodes

- `working_memory_node`: receives observations, maintains active episodes,
  computes novelty/arousal/focus, and publishes state, graph data, and
  consolidations.
- `long_term_memory_node`: consumes consolidated episodes, reinforces patterns,
  publishes summaries, and persists the memory JSON.
- `auditory_day_simulator`: publishes demo observations.
- `AuditoryMemoryPlugin`: rqt plugin for visualizing the graph, arousal, focus,
  and learned patterns.

## Topics

| Topic | Type | Use |
| --- | --- | --- |
| `/sound_observation` | `auditory_memory_msgs/AuditoryObservation` | Input from perception or the simulator. |
| `/auditory_memory/wm_state` | `auditory_memory_msgs/AuditoryWorkingMemoryState` | Active episodes, focus, and arousal. |
| `/auditory_memory/graph_viz` | `std_msgs/String` | JSON for the rqt graph. |
| `/auditory_memory/consolidation` | `auditory_memory_msgs/AuditoryEpisode` | Finished episodes for Long-Term Memory. |
| `/auditory_memory/ltm_patterns` | `std_msgs/String` | JSON summary of persistent patterns. |

## `AuditoryObservation` Input

Working Memory uses:

- `header.stamp` as observation time when it is nonzero.
- `header.frame_id` as fallback location.
- `pose` for room lookup when location configuration is available.
- `keywords[0]` as sound type when present.
- `description` as sound type fallback.

## rqt

The plugin appears under:

```text
Plugins -> Robot Tools -> Auditory Memory Graph Viewer
```

Main encoding:

- blue circle: sound type.
- green square: location.
- gray circle: concrete episode.
- red border: focused episode.
- orange arrow: `co_occurs`.
- purple arrow: `heard_in`.
- green arrow: `typical_for`.

The side panel shows arousal, focus, active episodes, recent history, and learned
patterns from `/auditory_memory/ltm_patterns`.

## Simulator

Available `auditory_day_simulator` modes:

- `natural`: full home-day scenario, paced for rqt.
- `fast`: compressed variant for quick testing.
- `anomaly`: unusual night events.
- `learning`: repeated days for watching pattern reinforcement.
- `learn_then_anomaly`: learns a routine, introduces anomalies, then keeps
  reinforcing.

Common parameters:

- `demo_mode`
- `publish_topic`
- `num_days`
- `speed_multiplier`
- `sim_duration_s`
- `sim_day_hours`

The simulator may log annotations such as `novelty_label` or `arousal_hint`, but
it does not publish them as algorithm control inputs. Novelty and arousal are
computed from memory.
