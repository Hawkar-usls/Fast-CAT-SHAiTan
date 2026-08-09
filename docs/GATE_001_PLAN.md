# PILOT_001 — Open-video frame-timing gate

## Target

```text
OPEN VIDEO
  -> RAW SHA-256
  -> PTS/FPS + codec time-base
  -> two-cat identity
  -> 48 CatFLW-compatible landmarks
  -> CatFACS-compatible facial-action onset
  -> deterministic same-action pairing
  -> delta-t in milliseconds + acquisition uncertainty
  -> SHA-256-bound result
  -> independent replay
```

## Frozen sources

1. `commons_hugging_2019` — affiliative candidate / primary source.
2. `commons_tomcats_conflict_2020` — non-affiliative control.

The order, action set, matching rule, confidence floors and no-postselection policy are frozen in [`../experiments/pilot_001/protocol.json`](../experiments/pilot_001/protocol.json) before the raw-video latency measurement.

## Gate decomposition

### G001-A — source truth

Requires exact raw bytes, SHA-256, licence/source identity, ffprobe replay, dimensions, duration, FPS and codec time-base. CI executes this automatically and a second verifier recomputes the raw hash and ffprobe metadata without importing the analysis module.

### G001-B — 48-landmark truth

Requires stable two-cat identity and exactly 48 finite CatFLW/Finka-compatible landmarks per admitted cat/frame. A generic cat detector is insufficient.

### G001-C — facial-action onset truth

Requires an allowed event source: independently frame-reviewed CatFACS-compatible labels or a separately validated Fast-CAT event detector. Ear movements `EAD103/EAD104` are primary endpoints; the secondary action set is frozen in the protocol.

### G001-D — latency replay

Uses source PTS, not wall-clock playback time. Pairing is deterministic: earliest unused same-action event by the other cat in the forward `<= 1000 ms` window. No-match is a valid preserved outcome.

### G001-E — claim admission

Only after G001-A through G001-D and independent replay may the state become:

```text
INDEPENDENT_FRAME_LEVEL_ESTIMATE = ESTABLISHED
```

Until then:

```text
INDEPENDENT_FRAME_LEVEL_ESTIMATE = NOT_ESTABLISHED
```

Passing this gate would establish a measurement for the admitted open-video events, **not** a universal feline reaction time.
