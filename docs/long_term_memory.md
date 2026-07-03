# Long-Term Memory

Long-Term Memory is persistent and cross-session. It is implemented as a
NetworkX directed graph serialized to JSON.

Long-Term Memory stores learned auditory patterns, not mainly raw past episodes.
The concrete `AuditoryEpisode` received during consolidation is used to update
pattern nodes, counters, histograms, and weighted edges.

## Consolidation

Working Memory publishes finished episodes on `/auditory_memory/consolidation`.
The Long-Term Memory node receives those messages and reinforces persistent
patterns.

For example, a consolidated episode like:

```text
08:05 kitchen: coffee_machine
```

reinforces patterns such as:

```text
sound:coffee_machine count += 1
sound:coffee_machine familiarity increases
sound:coffee_machine -> location:kitchen weight increases
location:kitchen -> sound:coffee_machine weight increases
coffee_machine morning time histogram increases
```

It does not write a permanent raw episode record to the LTM JSON file.

## Pattern Types

The current implementation updates:

- sound familiarity
- sound occurrence counts (`episode_count`)
- sound-location associations (`heard_in` edges)
- location-sound typicality (`typical_for` edges)
- sound-sound co-occurrence (`co_occurs` edges)
- approximate time-of-day patterns (`hour_hist` on sound nodes)
- optional `last_seen`, `first_seen`, `last_updated`, and `last_novelty`
  metadata for bookkeeping/pruning

## Persistence

The Long-Term Memory node persists graph data as JSON at `ltm_path`.

Default when launched from bringup:

```text
/home/lab/auditory_ws/auditory_memory_data/ltm.json
```

Default if the node is run directly without launch override:

```text
/tmp/auditory_ltm.json
```

Use a separate file for demos when you want to start from empty memory:

```bash
rm -f /tmp/auditory_ltm_demo.json
ros2 launch auditory_memory_bringup auditory_memory.launch.py \
  ltm_path:=/tmp/auditory_ltm_demo.json
```

## JSON Shape

The persistent file stores graph nodes and edges:

```json
{
  "nodes": [
    {
      "id": "sound:coffee_machine",
      "type": "sound_type",
      "sound_type": "coffee_machine",
      "episode_count": 4,
      "familiarity": 0.58,
      "hour_hist": [0, 0, 0]
    }
  ],
  "edges": [
    {
      "source": "sound:coffee_machine",
      "target": "location:kitchen",
      "relation_type": "heard_in",
      "weight": 0.72,
      "count": 4
    }
  ]
}
```

## Pattern Summary Topic

The Long-Term Memory node publishes compact pattern summaries on
`/auditory_memory/ltm_patterns` as `std_msgs/String` JSON. The rqt plugin uses
this topic for the `Long-Term Memory Patterns` panel.

The summary includes top sound-location, location-sound, co-occurrence,
time-of-day, sound familiarity, and recent in-memory pattern updates. Recent
updates are bounded and used for visualization/debugging; they are not a raw
episode database.

## Pruning

The current pruning logic can remove low-weight edges if they are older than the
configured threshold.

Relevant parameters:

- `ltm_prune_min_weight`
- `ltm_prune_older_than_s`
- `ltm_serialize_interval_s`
