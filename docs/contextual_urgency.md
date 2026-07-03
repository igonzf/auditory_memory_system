# Contextual Urgency

Contextual urgency is separate from base novelty.

Novelty asks: is this sound unexpected based on Long-Term Memory patterns?

Contextual urgency asks: is this sound more relevant because it follows a recent
high-novelty event?

## Recent High-Novelty Context

Working Memory keeps a short buffer of recent high-novelty context events. When
a new sound arrives, Working Memory can compare it with that buffer. If the new
sound follows a recent high-novelty event within the configured time window, it
can receive a contextual urgency boost.

For example:

```text
19:30 kitchen: glass_breaking
19:45 kitchen: voices
```

The voices may have their own base novelty, but they can become more urgent
because they occur after a recent high-novelty kitchen event.

## Simulator Annotations Are Not Used

The simulator logs fields such as `category`, `novelty_label`, and
`arousal_hint` for explanation. Those fields are not published to Working Memory
and do not control novelty, arousal, focus, or contextual urgency.

## Parameters

- `context_urgency_enabled`: enable or disable the mechanism.
- `context_urgency_window_s`: maximum simulated-time window for context.
- `context_urgency_min_delay_s`: minimum delay after the source event.
- `context_urgency_novelty_threshold`: novelty needed to enter the context
  buffer.
- `context_urgency_same_location_only`: require the later sound to occur in the
  same location.
- `context_urgency_boost`: how much urgency contributes to arousal evidence.
- `context_urgency_focus_weight`: how much urgency contributes to focus
  selection.
