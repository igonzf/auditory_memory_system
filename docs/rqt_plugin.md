# rqt Plugin

The rqt plugin is `AuditoryMemoryPlugin` and appears as:

```text
Plugins -> Robot Tools -> Auditory Memory Graph Viewer
```

It subscribes to:

- `/auditory_memory/graph_viz`
- `/auditory_memory/wm_state`
- `/auditory_memory/ltm_patterns`

It no longer displays a raw recent-consolidation episode list. The side panel
emphasizes learned Long-Term Memory patterns.

## Working Memory Graph

The main graph visualizes current Working Memory.

Node encoding:

- blue circle: `sound_type`
- green square: `location`
- gray circle: concrete `episode`
- larger node: higher activation
- more transparent node: lower activation
- red border: focused/currently most relevant episode

Edge encoding:

- orange arrow: `co_occurs`
- purple arrow: `heard_in`
- green arrow: `typical_for`
- thicker arrow: stronger weight

## Side Panel

The side panel shows:

- arousal value and progress bar
- focused sound and location
- active episodes
- novelty, contextual urgency, arousal contribution, co-occurring sounds, and
  consolidation readiness per active episode
- Long-Term Memory pattern summaries
- arousal history over the last 60 seconds

## Long-Term Memory Patterns Panel

The `Long-Term Memory Patterns` panel is textual and intentionally simple. It
shows top entries from `/auditory_memory/ltm_patterns`:

```text
Sound-location
- coffee_machine -> kitchen          w=0.72
- alarm -> bedroom                   w=0.68

Time-of-day
- coffee_machine -> morning          count=3
- alarm -> morning                   count=3

Co-occurrence
- tv_on <-> voices                   w=0.64
- door_opening <-> footsteps         w=0.58

Recent updates
- reinforced coffee_machine -> kitchen
- reinforced tv_on <-> voices
```

`w` means learned edge weight. `count` means reinforcement count or time-bin
count, depending on the pattern type.

## Controls

- Topic selector: change the graph JSON topic.
- Pause/Resume: freeze or resume display updates.
- Clear: reset local display state.
- Snapshot: save the current graph as a PNG in `~/auditory_memory_snapshots`.

## Demo Interpretation

During learning demos, routine sounds should gradually create and reinforce LTM
patterns. During anomaly moments, the graph should show increased novelty,
arousal, and focus for sounds with missing or violated pattern support.
