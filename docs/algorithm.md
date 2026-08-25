# Algorithm and Memory

Compact reference for the system's internal behavior.

## Working Memory

Working Memory is volatile and lives in RAM as a NetworkX directed graph. It
stores recent auditory episodes, sound nodes, location nodes, activations, recent
co-occurrences, focus, arousal, and consolidation state.

An episode represents a concrete sound in a location. If the same sound is heard
again in the same location while it is still active, the episode is updated;
otherwise, a new one is created. When it has not been heard for more than
`inactive_gap_s`, it is published for consolidation and later removed from
Working Memory according to `episode_ttl_s`.

If no reliable location is available, `unknown_location` is used internally. That
label is not treated as a real room unless explicitly enabled with
`learn_unknown_location_patterns`.

## Long-Term Memory

Long-Term Memory is persistent and is saved as JSON at `ltm_path`. It does not
primarily store raw episodes; it uses consolidated episodes to reinforce
patterns.

Current patterns:

- familiarity and count per sound type.
- sound-location associations.
- typical sounds per location.
- sound-sound co-occurrences.
- approximate time-of-day histograms.

An episode such as `08:05 kitchen: coffee_machine` reinforces the familiarity of
`coffee_machine`, its relation to `kitchen`, and its morning histogram. Repeated
routines increase weights and usually reduce the later novelty of equivalent
events.

## Novelty

Novelty estimates how much an observation violates learned patterns:

```text
novelty =
  0.40 * (1.0 - familiarity)
+ 0.45 * (1.0 - location_congruence)
+ 0.15 * (1.0 - time_expectedness)
```

- `familiarity`: whether the sound has already been learned.
- `location_congruence`: whether the sound fits the current location.
- `time_expectedness`: whether it usually occurs around the current time.

If location is missing, congruence uses the neutral
`location_missing_neutral_congruence` value instead of treating it as a room
mismatch.

## Arousal, Focus, and Contextual Urgency

Arousal is a global value from `0.0` to `1.0`. It increases with novel,
incongruent, or contextually urgent events, and decays over time.

Contextual urgency does not change base novelty. It can make a later sound more
relevant when it occurs shortly after a high-novelty event, for example
`glass_breaking` followed by `voices` in the same area.

Focus is selected from active episodes using novelty, location incongruence,
intensity, and contextual urgency. In rqt it is marked with a red border.

## Time

The logic uses `AuditoryObservation.header.stamp` when present. This lets
accelerated simulators keep simulated hours consistent for co-occurrence,
contextual urgency, and time expectedness. If the timestamp is empty or zero,
wall-clock time is used.
