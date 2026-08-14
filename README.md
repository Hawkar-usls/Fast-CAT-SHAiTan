<div align="center">

# Fast-CAT-SHAiTan
### Reproducible feline facial-response timing experiments

![Status](https://img.shields.io/badge/status-research%20prototype-f0ad4e)
![License](https://img.shields.io/badge/code-Apache--2.0-2f81f7)
![PILOT_001](https://img.shields.io/badge/PILOT__001-external%20review%20pending-6e7681)

`cat facial timing` · `CatFLW / CatFACS` · `temporal ML` · `SHA-256 provenance`

</div>

## Goal

Measure the delay between a facial action by one cat and the corresponding action by another cat:

```text
Δt_ms = (t_responder - t_signaller) * 1000
```

Fast-CAT treats video timing, visual measurement, model inference and claim admission as separate evidence layers. SHA-256 is used for integrity/lineage, not as a biological feature.

The project name is a tribute to **Shaitan**, the cat who inspired it; `SHA` in `SHAiTan` also reflects the provenance layer.

## Current state

| Gate | Status |
| --- | --- |
| Open source media | **ESTABLISHED** for PILOT_001 |
| Exact raw-media SHA-256 | **ESTABLISHED** |
| PTS / FPS / codec time-base | **ESTABLISHED + independently replayed** |
| Primary-source candidate 48-landmark coverage | **50/50 candidate frames; not landmark ground truth** |
| Conflict-control candidate 48-landmark coverage | **1218/1218 full-rate candidate frames; not landmark ground truth** |
| Deterministic face-aligned ear-motion triage | **ESTABLISHED AS TRIAGE ONLY** |
| Model-blinded EAD review package | **FROZEN** |
| Fail-closed independent-review ingestion / replay | **ESTABLISHED AS SOFTWARE GATE** |
| Two-reviewer exact-unanimity consensus | **ESTABLISHED AS SOFTWARE GATE** |
| Real independent blinded reviewers | **pending — at least 2 required** |
| Stable two-cat identity for biological claim scope | not established independently |
| CatFACS EAD103 / EAD104 action onset | not established |
| `Δt` from raw open video | not established |
| `INDEPENDENT_FRAME_LEVEL_ESTIMATE` | **NOT_ESTABLISHED** |

Machine-readable state: [`PROJECT_STATUS.json`](PROJECT_STATUS.json)

## PILOT_001 — open-video gate

Frozen sources:

1. `commons_hugging_2019` — affiliative candidate / primary source.
2. `commons_tomcats_conflict_2020` — non-affiliative control.

The exact downloaded media and stream timing have already passed independent replay:

| source | SHA-256 | video timing |
| --- | --- | --- |
| hugging | `1ac95b351424d63d944969e19949a925e502fbb380153aa404f99390c9845e2e` | 1440×1080, VP8, **120 fps**, 3.058 s |
| tomcats conflict | `79ea8a60c5aee25438ee70c2fff192ba953e89d29219c3d6ce5ed8e10e2078cf` | 640×480, VP9, **30 fps**, 45.485 s |

Frozen receipt: [`experiments/pilot_001/source_preflight.json`](experiments/pilot_001/source_preflight.json)

The current admission path is:

```text
OPEN VIDEO / RAW SHA-256 / PTS        PASS + independent replay
                    ↓
PINNED 48-LANDMARK CANDIDATE COVERAGE PASS_CANDIDATE_ONLY
  hugging: 50/50
  conflict control: 1218/1218
                    ↓
FACE-ALIGNED EAR-MOTION TRIAGE         ESTABLISHED AS TRIAGE ONLY
                    ↓
MODEL-BLINDED EAD REVIEW PACKAGE       FROZEN
                    ↓
REAL INDEPENDENT BLINDED REVIEWS       OPEN — at least 2 required
                    ↓
EXACT-UNANIMITY FRAME-STATE CONSENSUS  SOFTWARE GATE READY
                    ↓
EAD103 / EAD104 FIRST-VISIBLE ONSET    OPEN
                    ↓
Δt + event-local uncertainty           OPEN
                    ↓
FULL CLAIM / INDEPENDENT REPLAY         OPEN
```

Candidate landmark coverage is **not** landmark-accuracy validation, independent subject-identity proof, or CatFACS action annotation. No geometric motion rank is promoted to EAD103/EAD104.

The protocol is frozen before the latency measurement in [`experiments/pilot_001/protocol.json`](experiments/pilot_001/protocol.json). Primary facial actions are `EAD103` and `EAD104`; no-match windows are preserved and post-hoc source/action dropping is forbidden.

### Timing precision

Video PTS is authoritative. Nominal `frame_index / fps` is diagnostic only when PTS exists.

For frame-localized event onsets, the acquisition component of the `Δt` uncertainty is conservatively bounded by at least one nominal frame interval:

```text
hugging 120 fps  -> ±8.33 ms acquisition radius
control  30 fps  -> ±33.33 ms acquisition radius
```

Detector/action-onset localization error is **additional**; the figures above are not claims of total model accuracy.

Genesis-derived correction record: [`experiments/pilot_001/genesis_corrections.json`](experiments/pilot_001/genesis_corrections.json)

### Full-rate non-affiliative control

The conflict-control path is no longer limited to its original deterministic 83-frame preflight. The frozen full-rate gate in [`experiments/pilot_001/control_full_rate_gate.json`](experiments/pilot_001/control_full_rate_gate.json) processes every one of the **1218 decoded frames** with the pinned two-ROI 48-landmark backend.

The merged gate produced:

```text
selected decoded frames                 1218 / 1218
cat_C_brown_left valid candidate face   1218 / 1218
cat_D_gray_right valid candidate face   1218 / 1218
spatially distinct two-candidate frames 1218 / 1218
duplicate-face-risk frames              0
incomplete-ROI frames                    0
candidate coverage fraction              1.0
adjacent ear-motion transitions          2434 / 2434
```

This is `PASS_CANDIDATE_ONLY`: it establishes full-rate candidate geometry and deterministic triage availability for the control. It does **not** establish landmark accuracy, independent cat identity, EAD103/EAD104, action onset, mimicry, `Δt`, feline reaction latency, or `INDEPENDENT_FRAME_LEVEL_ESTIMATE`.

Two independent runs of the same Fast-CAT tree and pinned backend reproduced the same admission outcome and cardinalities, but the raw floating landmark geometry was not byte-identical. Fast-CAT therefore treats exact hashes as lineage receipts for each individual run, not as evidence that TFLite floating inference is bitwise deterministic across runs. A tolerance-based numerical reproducibility gate is the next parallel engineering task.

## Independent blinded review boundary

The software path for real review is already built. Each reviewer must submit the completed frozen form plus an attestation that binds the review to the exact model-blinded package. Ingestion rebinds the package, validates row states, re-derives onsets and matching, and is replayed by an independent verifier.

The multi-reviewer gate requires at least two distinct valid reviewer bundles. It uses **exact unanimity** for `identity_confirmed` and the four EAD103/EAD104 ear-state channels. Any non-unanimous cell becomes `DISAGREEMENT`; it is not averaged, majority-voted, model-filled or silently dropped. Consensus onsets can arise only from unanimous adjacent-frame `ABSENT -> PRESENT` transitions with unanimous identity confirmation.

Synthetic reviewer fixtures test the software boundary only and are never biological evidence. No real independent reviewer bundle has yet been admitted.

## PILOT_000 — software fixture replay

PILOT_000 replays the **sample events in the authors' public `facial_mimicry_analysis.py` code**. That upstream file explicitly marks the sequence as an example and says the real data still need to be loaded.

The deterministic replay gives `300 ms`, `150 ms`, and `150 ms`, but these values are only a software/replay fixture. They are **not attributed to the raw study dataset and are not measured feline reaction times**.

```bash
python scripts/replay_pilot_000.py
```

Frozen record: [`experiments/pilot_000/pilot_000.json`](experiments/pilot_000/pilot_000.json)

## Model architecture

Fast-CAT separates three roles:

- **CatGPT baseline** — interpretable autoregressive transition/n-gram/Slime-Trace baseline; it does not create timestamp truth.
- **48-landmark detector** — CatFLW-compatible visual measurement for ears, eyes, nose, mouth and face geometry.
- **Temporal model** — candidate attention/Transformer layer for event onset and cross-cat temporal structure, validated only after a frozen train/validation split.

Model notes: [`docs/MODEL_SELECTION.md`](docs/MODEL_SELECTION.md)  
Landmark/event boundary: [`docs/LANDMARK_EVENT_ADMISSION.md`](docs/LANDMARK_EVENT_ADMISSION.md)

## JANUS method reuse

Fast-CAT reuses bounded engineering ideas from sibling repositories:

- **Janus-Fundamentum** — evidence discipline, negative-result preservation and strict claim ceilings;
- **Janus_Genesis** — canonical hashing, fail-closed replay, preregistration and sequential false-positive accounting;
- **janus-lapis** — `PASS / REVIEW / REJECT` candidate-triage structure, not its domain-specific numerical constants;
- **Janus-Demiurge** — ordinary GP/EI Bayesian optimization on a frozen validation split only.

Speculative legacy heuristics such as digital-root resonance, tachyonic filters and `filter_37` are explicitly excluded from Fast-CAT scientific calibration.

Details: [`docs/CROSS_REPO_METHOD.md`](docs/CROSS_REPO_METHOD.md)

## Scientific boundaries

Fast-CAT does not currently claim a universal feline reaction time, intentional communication from temporal correlation alone, equivalence between an AI detector and expert CatFACS annotation, or sub-frame precision without a sub-frame measurement method.

Negative and inconclusive results are valid outcomes.

## Reproducibility

```bash
python scripts/replay_pilot_000.py
python -m unittest discover -s tests -v
```

PILOT_001 CI downloads frozen open media, recomputes raw SHA-256, re-runs `ffprobe`, checks source manifests, replays decoded PTS/pixels, runs pinned candidate-landmark backends and publishes exact receipts. Floating model outputs are not assumed to be bitwise deterministic merely because the source/backend revisions are pinned.

## Related work

- Martvel et al. (2024), *Computational investigation of the social function of domestic cat facial signals* — DOI `10.1038/s41598-024-79216-2`
- Martvel et al. (2024), *Automated Detection of Cat Facial Landmarks* — CatFLW / 48-landmark reference
- Authors' public analysis code: `teddy4445/social_function_of_domestic_facial_signals`

## License

Repository-authored code and documentation are licensed under **Apache License 2.0** unless a file states otherwise. Third-party papers, datasets, models and media retain their original licences and attribution requirements.
