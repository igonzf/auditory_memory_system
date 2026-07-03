# Topics And Messages

## `/sound_observation`

Type: `auditory_memory_msgs/AuditoryObservation`

Input topic for pre-processed auditory observations. The system does not
classify raw audio; it expects this message from an upstream perception system or
the simulator.

Working Memory uses:

- `header.stamp` for observation time when present
- `header.frame_id` as fallback location if no configured room contains the pose
- `pose` for room lookup when location config is available
- `keywords[0]` as sound type when present
- `description` as fallback sound type

## `/auditory_memory/wm_state`

Type: `auditory_memory_msgs/AuditoryWorkingMemoryState`

Published by Working Memory. Contains active episodes, focused sound/location,
and arousal level.

## `/auditory_memory/graph_viz`

Type: `std_msgs/String`

JSON payload for rqt graph visualization. Contains Working Memory nodes, edges,
arousal, focused sound/location, and recent high-novelty context metadata.

## `/auditory_memory/consolidation`

Type: `auditory_memory_msgs/AuditoryEpisode`

Published by Working Memory when an episode becomes inactive and ready for
consolidation. Consumed by Long-Term Memory to reinforce patterns.

This topic carries concrete episode data as an update input. Long-Term Memory
does not persist these messages as a raw episode database.

## `/auditory_memory/ltm_patterns`

Type: `std_msgs/String`

JSON payload published by Long-Term Memory with compact learned pattern
summaries. Used by the rqt `Long-Term Memory Patterns` panel.

The payload includes:

- `sound_patterns`
- `sound_location_patterns`
- `location_sound_patterns`
- `co_occurrence_patterns`
- `time_patterns`
- `recent_updates`
