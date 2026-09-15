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

Fast-CAT treats video timing, visual measurement, model inference, human review and claim admission as separate evidence layers. SHA-256 is used for integrity/lineage, not as a biological feature.

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
| Numerical reproducibility of pinned candidate geometry | **VALIDATED WITHIN FROZEN TOLERANCES; not bitwise float identity** |
| Model-blinded EAD review content | **FROZEN + transport-independent exact-content identity** |
| Fail-closed independent-review ingestion / replay | **ESTABLISHED AS SOFTWARE GATE, active v1.2/v1.1** |
| Reviewer collection readiness | **ESTABLISHED — waiting for first real reviewer** |
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

The exact downloaded media and stream timing have passed independent replay:

| source | SHA-256 | video timing |
| --- | --- | --- |
| hugging | `1ac95b351424d63d944969e19949a925e502fbb380153aa404f99390c9845e2e` | 1440×1080, VP8, **120 fps**, 3.058 s |
| tomcats conflict | `79ea8a60c5aee25438ee70c2fff192ba953e89d29219c3d6ce5ed8e10e2078cf` | 640×480, VP9, **30 fps**, 45.485 s |

Frozen receipt: [`experiments/pilot_001/source_preflight.json`](experiments/pilot_001/source_preflight.json)

The current admission path is:

```text
OPEN VIDEO / RAW SHA-256 / DECODED PTS      PASS + independent replay
                    ↓
PINNED 48-LANDMARK CANDIDATE COVERAGE       PASS_CANDIDATE_ONLY
  hugging: 50/50
  conflict control: 1218/1218
                    ↓
FACE-ALIGNED EAR-MOTION TRIAGE               ESTABLISHED AS TRIAGE ONLY
                    ↓
FROZEN MODEL-BLINDED PACKAGE CONTENT         EXACT CONTENT IDENTITY
                    ↓
REAL REVIEWER #1                              WAITING_FOR_FIRST_REVIEWER
                    ↓
REAL REVIEWER #2                              WAITING_FOR_SECOND_REVIEWER
                    ↓
REVIEWER COLLECTION                          READY_FOR_CONSENSUS
                    ↓
EXACT-UNANIMITY FRAME-STATE CONSENSUS        disagreement preserved
                    ↓
EAD103 / EAD104 FIRST-VISIBLE ONSET          OPEN
                    ↓
Δt + event-local uncertainty                 OPEN
                    ↓
FULL CLAIM / INDEPENDENT REPLAY               OPEN
```

Candidate landmark coverage is **not** landmark-accuracy validation, independent subject-identity proof, or CatFACS action annotation. No geometric motion rank is promoted to EAD103/EAD104.

The biological protocol was frozen before latency measurement in [`experiments/pilot_001/protocol.json`](experiments/pilot_001/protocol.json). Primary facial actions are `EAD103` and `EAD104`; no-match windows are preserved and post-hoc source/action dropping is forbidden.

### Timing precision

Video PTS is authoritative. Nominal `frame_index / fps` is diagnostic only when PTS exists.

For frame-localized event onsets, acquisition uncertainty is event-local: the signaller and responder are each bracketed by their immediately preceding visible `ABSENT` frame and first visible `PRESENT` frame. Detector/reviewer localization uncertainty is additional; no sub-frame biological precision is claimed without a sub-frame measurement method.

Genesis-derived correction record: [`experiments/pilot_001/genesis_corrections.json`](experiments/pilot_001/genesis_corrections.json)

### Full-rate non-affiliative control

The conflict-control path is no longer limited to its original deterministic 83-frame preflight. The frozen full-rate gate in [`experiments/pilot_001/control_full_rate_gate.json`](experiments/pilot_001/control_full_rate_gate.json) processes every one of the **1218 decoded frames** with the pinned two-ROI 48-landmark backend.

The full-rate result is:

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

### Numerical reproducibility

Independent full-rate runs of the same frozen source/tree/backend reproduced the same 1218/1218 coverage, zero duplicate/incomplete counts and exact 2434 transition-key set, while raw floating landmark geometry showed tiny non-bitwise jitter.

Fast-CAT therefore does **not** pretend that pinned TFLite inference is byte-identical across runs. A numerical reproducibility protocol was frozen before a fresh validation replication. That fresh run reproduced all semantic invariants, both cats' top-10 transition sets at 10/10, and passed all seven frozen floating-difference limits.

Current status:

`VALIDATED_WITHIN_FROZEN_NUMERICAL_TOLERANCE`

The tolerance gate strengthens candidate-geometry reproducibility only; it does not convert candidate landmarks into CatFACS ground truth.

## Durable model-blinded reviewer package

The scientific reviewer input is no longer identified solely by one expiring GitHub Actions ZIP container.

The already-frozen blinded package now has a transport-independent content identity:

- content identity file SHA-256: `87877d69e5fcfd44433b93106740ef641c320a8037b06aefe281fff9179378fd`
- package manifest SHA-256: `85bf6a190377a304b607bd611cd7d9476e521b98682286f4d9cfb47d5878e3e4`
- manifest files-payload SHA-256: `2a550d1d32fff07757c6838f224a63fa5d87a00017b4dcc110154bd75fd99513`
- frame manifest SHA-256: `0271018446726ccabd3be78e29c426e03d772e2bc01bb40ceb32ff246ae51c67`
- blank review form SHA-256: `b464040c69491ac1ce7e1083f2745a85361fe3884cce1b37d6c9c7bae946622d`
- payload entries: **53**

Identity record: [`experiments/pilot_001/blinded_review_content_identity.json`](experiments/pilot_001/blinded_review_content_identity.json)

A mirror or repacked ZIP may have a different **outer** SHA-256. It is admissible only if `scripts/verify_blinded_package_content.py` proves every canonical package byte against the frozen manifest. Missing files, modified bytes, unexpected injected files, unsafe paths and duplicate ZIP member names fail closed.

The original Actions artifact remains historical origin provenance. Its outer ZIP digest is not the long-term scientific admission authority.

## Independent blinded review boundary

No real reviewer submission has been received yet.

The active submission path uses:

- submission protocol `v1.2`;
- reviewer attestation `v1.1`;
- production ingestion report `v1.2`;
- independent verifier report `v1.1`;
- reviewer collection protocol `v1.1`;
- unchanged exact-unanimity consensus rule `v1.0`.

A reviewer first verifies the exact canonical blinded package content, completes all 100 rows without seeing Fast-CAT model-derived evidence, freezes the completed CSV SHA-256, and submits the completed CSV + frozen frame manifest + attestation. Production ingestion rebinds the canonical package content, validates rows, derives all admissible `ABSENT -> PRESENT` onsets and deterministic same-action pairing, then an independently implemented verifier recomputes the result.

Reviewer handoff: [`experiments/pilot_001/REVIEWER_HANDOFF.md`](experiments/pilot_001/REVIEWER_HANDOFF.md)

The collection gate has four explicit machine states:

```text
WAITING_FOR_FIRST_REVIEWER
WAITING_FOR_SECOND_REVIEWER
READY_FOR_CONSENSUS
INVALID_COLLECTION
```

Waiting states are not software failures. Invalid artifacts fail closed. At least two admissible distinct reviewer bundles are required before consensus.

The consensus gate uses **exact unanimity** for `identity_confirmed` and all four EAD103/EAD104 ear-state channels. Any non-unanimous cell becomes `DISAGREEMENT`; it is not averaged, majority-voted, model-filled or silently dropped. Consensus onsets can arise only from unanimous adjacent-frame `ABSENT -> PRESENT` transitions with unanimous identity confirmation.

Two genuinely independent reviewers may produce byte-identical completed CSV files; forcing different CSV hashes would be a false independence criterion. Likewise, they may receive byte-distinct ZIP transports containing the same exact canonical package content. Distinct reviewer IDs and attestation identities are required, but software explicitly does **not** claim to prove human personhood, institutional independence, competence truthfulness or absence of off-channel collusion.

Synthetic reviewer fixtures test the software boundary only and are never biological evidence.

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

Negative, zero-event, zero-match, disagreement and inconclusive results are valid outcomes.

## Reproducibility

```bash
python scripts/replay_pilot_000.py
python -m unittest discover -s tests -v
```

PILOT_001 CI downloads frozen open media, recomputes raw SHA-256, re-runs stream checks, replays decoded PTS/pixels, runs pinned candidate-landmark backends, verifies the frozen blinded-package content identity, replays synthetic reviewer boundaries and publishes exact receipts. Floating model outputs are not assumed to be bitwise deterministic merely because the source/backend revisions are pinned.

## Related work

- Martvel et al. (2024), *Computational investigation of the social function of domestic cat facial signals* — DOI `10.1038/s41598-024-79216-2`
- Martvel et al. (2024), *Automated Detection of Cat Facial Landmarks* — CatFLW / 48-landmark reference
- Authors' public analysis code: `teddy4445/social_function_of_domestic_facial_signals`

## License

Repository-authored code and documentation are licensed under **Apache License 2.0** unless a file states otherwise. Third-party papers, datasets, models and media retain their original licences and attribution requirements.
