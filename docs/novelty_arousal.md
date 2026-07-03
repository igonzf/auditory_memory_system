# Novelty And Arousal

Novelty estimates how unexpected a sound is in its current context. Arousal is
the system's current global alertness/relevance state.

## Novelty Inputs

The current novelty calculation uses three Long-Term Memory values:

- sound familiarity: whether the sound has been heard before
- location congruence: whether the sound is expected in the current location
- time expectedness: whether the sound usually happens around the current hour

## Formula

The current implementation computes:

```text
novelty =
  0.40 * (1.0 - familiarity)
+ 0.45 * (1.0 - location_congruence)
+ 0.15 * (1.0 - time_expectedness)
```

Each component is clamped to the range `0.0` to `1.0`.

## Familiarity

Familiarity is stored on sound nodes in Long-Term Memory. It increases when a
sound is consolidated repeatedly.

## Location Congruence

Location congruence is derived from LTM location-to-sound typicality. If a sound
has often occurred in a room, the location congruence for that sound in that
room increases.

## Time Expectedness

Time expectedness is derived from the sound's per-hour histogram. A sound heard
at a commonly learned hour has higher time expectedness than the same sound at a
rare hour.

## Arousal

Arousal increases when high-novelty or contextually urgent observations arrive.
It decays over time when no important sound continues.

The current Working Memory contribution is based on novelty plus an optional
contextual urgency boost:

```text
arousal_evidence = novelty + context_urgency_boost * contextual_urgency
```

The result is clamped to `0.0` to `1.0`.

## Novelty Versus Arousal

Novelty is an estimate for one observation/episode in context. Arousal is a
global state that accumulates evidence and decays over time. A sound can have
moderate base novelty but still become highly relevant if it follows a recent
high-novelty event through contextual urgency.
