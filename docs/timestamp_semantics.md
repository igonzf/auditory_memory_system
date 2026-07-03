# Timestamp Semantics

Behavioral logic uses observation timestamps when available.

## Observation Time

Working Memory uses `AuditoryObservation.header.stamp` as the observation time
when it is present and nonzero. This is important for simulator demos: a sound at
simulated `19:45` is treated as 15 simulated minutes after a sound at simulated
`19:30`, even if both messages arrive only seconds apart in wall-clock time.

If an observation has an empty or zero timestamp, Working Memory falls back to
wall-clock time.

## Uses Of Observation/Simulated Time

Observation timestamps are used for:

- episode `started_at`
- episode `last_heard`
- time-of-day expectedness in Long-Term Memory novelty evaluation
- sound co-occurrence windows
- contextual urgency windows
- consolidation timing through the Working Memory logical clock

## Wall-Clock Time

Visual activation and arousal decay use wall-clock timer intervals so rqt remains
readable during accelerated simulator runs.

Long-Term Memory persistence metadata such as `first_seen` and `last_updated`
uses wall-clock time for bookkeeping and pruning. This metadata is not used for
novelty, co-occurrence, or contextual urgency decisions.
