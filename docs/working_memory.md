# Working Memory

Working Memory is short-term and volatile. It is implemented as a NetworkX
directed graph in RAM and stores recent concrete auditory episodes.

## Stored State

Working Memory stores:

- active sound episodes
- sound type nodes
- location nodes
- episode nodes
- recent sound-sound co-occurrence
- recent sound-location associations
- activation levels
- focused sound/location
- global arousal level
- consolidation readiness

## Episodes

An episode represents a concrete recent sound in a location. If the same sound is
heard again in the same location while active, the existing episode is updated.
Otherwise, a new episode node is created.

Episode fields include sound type, location, start time, last-heard time,
co-occurring sounds, intensity, novelty, location congruence, contextual urgency,
arousal contribution, and consolidation state.

## Activation And Decay

Sound and location activation values increase when observations arrive and decay
over time. Short-term co-occurrence edges also decay in Working Memory.

## Focus

The focused sound is selected from active, unconsolidated episodes using novelty,
location incongruence, intensity, and contextual urgency. The focused episode is
shown in rqt with a red border.

## Arousal

Arousal is a global value from `0.0` to `1.0`. It increases when observations are
novel, location-incongruent, or contextually urgent. It decays over time.

## Co-Occurrence

Sounds heard close together are treated as co-occurring. The current
implementation uses `co_occurrence_window_s` to decide whether two active
episodes occurred close enough to reinforce short-term co-occurrence.

## Consolidation

When an episode has not been heard for longer than `inactive_gap_s`, it becomes
ready for consolidation. Working Memory publishes it on
`/auditory_memory/consolidation` and marks it consolidated. Old consolidated
episodes disappear from Working Memory after `episode_ttl_s`.

The consolidated `AuditoryEpisode` is an update input for Long-Term Memory. It is
not intended to become a permanent raw episode record.

## Relevant Parameters

- `observation_topic`
- `state_topic`
- `graph_viz_topic`
- `consolidation_topic`
- `timer_hz`
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
