<div align="center">

# Fast-CAT-SHAiTan
### Reproducible feline facial-response timing experiments

![Status](https://img.shields.io/badge/status-research%20prototype-f0ad4e)
![License](https://img.shields.io/badge/code-Apache--2.0-2f81f7)
![PILOT_001](https://img.shields.io/badge/PILOT__001-landmark%20gate%20open-6e7681)

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
| Stable two-cat identity through event intervals | pending |
| 48 CatFLW-compatible landmarks | pending admission |
| CatFACS-compatible facial-action onset | not established |
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

The remaining admission path is:

```text
OPEN VIDEO                 PASS
    ↓
RAW SHA-256                PASS
    ↓
PTS / FPS / time-base      PASS + independent replay
    ↓
TWO-CAT ID                 OPEN
    ↓
48 LANDMARKS               OPEN
    ↓
FACIAL-ACTION ONSET        OPEN
    ↓
Δt + uncertainty           OPEN
    ↓
INDEPENDENT REPLAY         OPEN
```

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

PILOT_001 source CI downloads the frozen open media, recomputes raw SHA-256, re-runs `ffprobe`, checks the source manifest, executes an independent verifier and publishes receipts as a workflow artifact.

## Related work

- Martvel et al. (2024), *Computational investigation of the social function of domestic cat facial signals* — DOI `10.1038/s41598-024-79216-2`
- Martvel et al. (2024), *Automated Detection of Cat Facial Landmarks* — CatFLW / 48-landmark reference
- Authors' public analysis code: `teddy4445/social_function_of_domestic_facial_signals`

## License

Repository-authored code and documentation are licensed under **Apache License 2.0** unless a file states otherwise. Third-party papers, datasets, models and media retain their original licences and attribution requirements.
