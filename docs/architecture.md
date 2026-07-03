# Architecture

## Packages

- `auditory_memory_msgs`: ROS 2 message definitions.
- `auditory_memory_core`: Working Memory, Long-Term Memory, simulators, and rqt
  plugin.
- `auditory_memory_bringup`: launch files.

## Main Nodes

- `working_memory_node`: subscribes to observations, maintains active episodes,
  computes novelty/arousal/focus, publishes graph/state, and publishes finished
  episodes for consolidation.
- `long_term_memory_node`: subscribes to consolidated episodes, reinforces
  persistent pattern graph data, publishes pattern summaries, and saves JSON.
- `auditory_day_simulator`: publishes demo `AuditoryObservation` messages.
- `AuditoryMemoryPlugin`: rqt plugin for visualizing Working Memory and learned
  Long-Term Memory patterns.

## Topic Flow

```text
/sound_observation
  -> working_memory_node
      -> /auditory_memory/wm_state
      -> /auditory_memory/graph_viz
      -> /auditory_memory/consolidation
          -> long_term_memory_node
              -> persistent LTM JSON
              -> /auditory_memory/ltm_patterns
                  -> rqt plugin
```

The Working Memory node also keeps a local Long-Term Memory model loaded from
the same `ltm_path` so novelty can adapt immediately during a run. The dedicated
Long-Term Memory node is responsible for persistence and the public pattern
summary topic.

## Processing Steps

1. `AuditoryObservation` arrives on `/sound_observation`.
2. The Working Memory node extracts sound type, location, and timestamp.
3. Working Memory creates or updates an active episode.
4. Long-Term Memory is queried for familiarity, location congruence, and time
   expectedness.
5. Novelty is computed from those LTM values.
6. Arousal and focus are updated.
7. Recent co-occurrence relations are updated in Working Memory.
8. When an episode becomes inactive, Working Memory publishes it on
   `/auditory_memory/consolidation`.
9. Long-Term Memory uses the consolidated episode to reinforce learned patterns.
10. rqt visualizes Working Memory graph data and Long-Term Memory pattern
    summaries.
