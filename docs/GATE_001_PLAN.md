# PILOT_001 Gate Plan

This file is a staging marker for the next Fast-CAT-SHAiTan gate.

Target pipeline:

```text
OPEN VIDEO
  -> RAW SHA-256
  -> PTS/FPS / time-base validation
  -> two-cat identity tracking
  -> 48 feline landmarks / CatFACS-compatible features
  -> facial-action onset detection
  -> same-action cross-cat matching within <= 1000 ms
  -> delta-t distribution in milliseconds
  -> uncertainty / abstention
  -> SHA-256-bound experiment receipt
```

Admission rule:

`INDEPENDENT_FRAME_LEVEL_ESTIMATE = ESTABLISHED` may be set only after raw media bytes, stream timing metadata, frame-level event tables, model/config identity, and deterministic replay all agree on an independently measured result.

Until then:

```text
INDEPENDENT_FRAME_LEVEL_ESTIMATE = NOT_ESTABLISHED
```
