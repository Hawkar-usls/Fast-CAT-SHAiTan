# Model Selection

## Existing CatGPT baseline

A pre-existing `CatGPT.py` prototype from the JANUS working set is a useful starting point for Fast-CAT-SHAiTan.

Its current design is a compact **statistical autoregressive model**, not a neural Transformer. It represents a cat observation with behavioral/context variables and numeric features including ear positions, head/body variables, motion, tail, pupil, and related context. It learns:

- behavior-transition counts conditioned on context;
- previous → current → next n-grams;
- motion statistics (`dx`, `dy`, `dvx`, `dvy`, `dt`);
- feature ranges;
- `Slime Trace`, a bounded reinforcement of repeatedly observed transitions;
- JSON checkpoint/resume state.

That makes CatGPT valuable as a transparent baseline: its temporal decisions can be inspected and replayed without a large opaque model.

## What should be reused

For the first Fast-CAT baseline, preserve the useful ideas rather than pretending the existing predictor already solves facial mimicry:

```text
CatGPT observation sequence
        ↓
context-conditioned transition memory
        ↓
ngram / transition evidence
        ↓
Slime Trace temporal reinforcement
        ↓
calibrated candidate event transition
```

The existing ear-related state is especially relevant, but the target representation needs to move from broad behavior labels such as `watch`, `walk`, or `play` toward facial-action events and onset timestamps.

## Fast-CAT temporal representation

A candidate per-frame record should eventually look like:

```json
{
  "video_id": "...",
  "cat_id": "A",
  "frame_index": 1203,
  "pts_s": 20.050,
  "face_confidence": 0.98,
  "landmarks": "48-point feline landmark vector or reference",
  "actions": {
    "AU25": 0.03,
    "AU26": 0.01,
    "EAD103": 0.81,
    "EAD104": 0.12
  }
}
```

Event detection then converts frame probabilities into explicit onset/apex/offset records. Matching is performed only after stable cat identity and timing metadata are available.

## Baseline A — CatGPT-derived temporal statistics

Use a small interpretable model first:

1. tokenize facial-action onsets and local context;
2. learn action transitions / n-grams per cat and interaction context;
3. learn empirical `Δt` distributions instead of only next-position motion;
4. use a bounded Slime-Trace-like memory for recurrent transition support;
5. serialize every learned state and bind it to its training-data SHA-256.

This baseline should be able to fail clearly when evidence is weak.

## Candidate B — temporal attention / Transformer

A dedicated temporal model can then consume short windows of per-frame feline facial landmarks or CatFACS-compatible features.

Possible input window:

```text
cat A: [t-500 ms ... t+1000 ms]
cat B: [t-500 ms ... t+1000 ms]
```

Possible outputs:

- action onset probabilities per frame;
- paired-action probability;
- estimated response latency;
- calibrated confidence / abstention score.

The neural model must not be allowed to silently override timestamp truth or source metadata.

## Evaluation rules

To avoid leakage and inflated results:

- split by source video / interaction, not by random frames from the same clip;
- where identities are known, prefer cat-disjoint evaluation where feasible;
- report frame resolution and timing resolution separately from model error;
- preserve negative examples and no-match windows;
- compare against simple baselines before claiming a Transformer improvement;
- do not train and evaluate on duplicated/transcoded versions of the same source clip without grouping them together;
- hash source manifests, model configuration, weights, and final event tables.

## Current decision

```text
CATGPT_FOUND = TRUE
CATGPT_IS_TRANSFORMER = FALSE
CATGPT_BASELINE_REUSE = APPROVED_FOR_PROTOTYPING
TEMPORAL_TRANSFORMER = CANDIDATE_NOT_YET_VALIDATED
RAW_VIDEO_EVENT_DETECTOR = NOT_YET_VALIDATED
```
