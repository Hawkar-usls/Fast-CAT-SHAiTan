# PILOT_001 — Open-video frame-timing gate

## Target

```text
OPEN VIDEO
  -> RAW SHA-256
  -> stream metadata
  -> full decoded-frame PTS ledger
  -> two-cat identity
  -> 48 CatFLW-compatible landmarks
  -> CatFACS-compatible first-visible onset + previous absent frame
  -> deterministic same-action pairing
  -> delta-t point estimate + decoded-PTS acquisition interval
  -> SHA-256-bound result
  -> independent replay
```

## Frozen sources

1. `commons_hugging_2019` — affiliative candidate / primary source.
2. `commons_tomcats_conflict_2020` — non-affiliative control.

The order, action set, matching rule, confidence floors and no-postselection policy are frozen in [`../experiments/pilot_001/protocol.json`](../experiments/pilot_001/protocol.json) before the raw-video latency measurement.

## Gate decomposition

### G001-A — source truth

Requires exact raw bytes, SHA-256, licence/source identity, ffprobe stream metadata, dimensions, duration and codec time-base. CI executes this automatically and a second verifier recomputes the raw hash and stream metadata without importing the analysis module.

### G001-A2 — decoded-frame timing truth

Header `avg_frame_rate` / `r_frame_rate` values are **diagnostic only**. Final event timing comes from the full decoded-frame PTS sequence.

This distinction is mandatory because the frozen hugging source advertises `120/1` in its stream header but the independently replayed decoded ledger contains only 50 frames from PTS 0.000 s through 3.050 s, with adjacent decoded-frame gaps of 58–67 ms. The control source contains 1,218 decoded frames with mostly 33 ms gaps and observed gaps up to 167 ms.

Therefore `frame_index / nominal_fps` and `1000 / header_fps` are forbidden as authoritative timing or acquisition-uncertainty channels when decoded PTS is available.

### G001-B — 48-landmark truth

Requires stable two-cat identity and exactly 48 finite CatFLW/Finka-compatible landmarks per admitted cat/frame **plus a justified landmark-accuracy/confidence channel**. Finite geometry from an external detector is candidate evidence, not ground truth. A generic cat detector or body-detection confidence is insufficient.

### G001-C — facial-action onset truth

Requires an allowed event source: independently frame-reviewed CatFACS-compatible labels or a separately validated Fast-CAT event detector. Ear movements `EAD103/EAD104` are primary endpoints; the secondary action set is frozen in the protocol.

For each admitted first-visible onset, two decoded PTS values are required:

```text
previous_absent_pts_s < onset_pts_s
```

The former is the immediately previous reviewed decoded frame where the action is absent; the latter is the first reviewed decoded frame where the action is present.

### G001-D — latency replay

Pairing remains deterministic: earliest unused same-action event by the other cat in the forward `<= 1000 ms` point-estimate window. No-match is a valid preserved outcome.

For signaller bracket `(s_prev, s]` and responder bracket `(r_prev, r]`:

```text
point_ms = (r - s) * 1000
lower_ms = (r_prev - s) * 1000
upper_ms = (r - s_prev) * 1000
```

Thus each reported latency carries an **event-local acquisition interval derived from actual decoded PTS**, not a global nominal-FPS radius. Detector/reviewer localization uncertainty is additional.

### G001-E — claim admission

Only after G001-A/A2 through G001-D and independent replay may the state become:

```text
INDEPENDENT_FRAME_LEVEL_ESTIMATE = ESTABLISHED
```

Until then:

```text
INDEPENDENT_FRAME_LEVEL_ESTIMATE = NOT_ESTABLISHED
```

Passing this gate would establish a measurement for the admitted open-video events, **not** a universal feline reaction time.
