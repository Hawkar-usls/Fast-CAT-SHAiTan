# 48-landmark and facial-action admission boundary

PILOT_001 must not infer millisecond reaction time directly from generic object tracking or from a visually plausible ear twitch.

## Reference scientific representation

The target representation is the CatFLW/Finka 48-landmark facial scheme. The published ELD detector family reports roughly 2.9 NME (inter-ocular-distance normalized) on CatFLW, and the 2024 social-signal study used a 48-landmark pipeline together with YOLOv8 / BoT-SORT identity tracking.

This is a **reference performance context**, not an automatic acceptance threshold for our open Wikimedia clips.

## PILOT_001 admission

For a pair to enter a latency result:

1. raw source bytes and timing metadata must pass the source preflight;
2. both cats must have stable IDs through the relevant interval;
3. every supporting frame must contain exactly 48 finite landmark coordinates;
4. landmark confidence must satisfy the frozen protocol threshold;
5. the action label and onset frame must come from an allowed source (`manual_catfacs_frame_review` or a separately validated Fast-CAT event model);
6. the action must belong to the preregistered action set;
7. the responder event must occur after the signaller event and within 1000 ms;
8. a response event may be consumed only once;
9. no event/source may be dropped after seeing whether it improves the result;
10. latency uncertainty must include acquisition/frame quantization.

## Precision

Use frame/video **PTS** as timing truth. Do not derive authoritative timestamps from `frame_index / nominal_fps` when PTS is available.

If event onset is localized only to a frame, a point estimate can be reported at that PTS, but the delta between two frame-quantized onsets carries a conservative acquisition quantization bound of at least one nominal frame interval.

For example, 60 fps implies a nominal interval of about 16.67 ms. That does not mean the detector itself is accurate to 16.67 ms; event-localization error is an additional term.

## Gate meaning

`INDEPENDENT_FRAME_LEVEL_ESTIMATE = ESTABLISHED` means exact media is bound, timing is replayable, valid 48-landmark evidence exists, action onsets pass the frozen rule, and matching/delta-t are replayed independently.

It does **not** mean a universal cat reaction time has been discovered.
