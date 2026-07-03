# Overview

The auditory memory system adds contextual memory to a robot audio pipeline.

It does not classify raw audio. It receives pre-processed
`AuditoryObservation` messages from an upstream perception system and adds:

- short-term auditory episodes
- location context
- temporal regularity
- novelty estimates
- arousal and focus state
- learned Long-Term Memory patterns

The system is intended to answer questions such as:

- Has this sound been heard before?
- Is this sound normal in this room?
- Is this sound normal at this time of day?
- Which sounds tend to occur together?
- Which current sound should be considered most relevant?

It does not currently implement robot reactions. The memory system creates the
conditions for future behavior modules to react to novelty, urgency, or learned
routine violations.

## Processing Flow

When a sound arrives:

```text
AuditoryObservation received
-> sound/location/time extracted
-> Working Memory creates or updates an active episode
-> Long-Term Memory is queried for familiarity, location congruence, and time expectedness
-> novelty is computed
-> arousal is updated
-> focus is selected
-> co-occurrence relations are updated
-> inactive episodes are consolidated
-> Long-Term Memory patterns are reinforced
-> rqt visualizes graph, arousal, focus, and learned patterns
```

## Main Concepts

- Working Memory stores recent concrete auditory episodes.
- Long-Term Memory stores learned auditory patterns, not mainly raw episode
  history.
- Consolidation means a finished Working Memory episode is used to reinforce
  Long-Term Memory patterns.
- Novelty estimates how unexpected a sound is in context.
- Arousal is the current global relevance/alertness state.
- Contextual urgency can make a later sound more relevant because it follows a
  recent high-novelty event.
