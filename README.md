<div align="center">

# Fast-CAT-SHAiTan
### Cryptographically reproducible feline facial-response timing experiments

![Status](https://img.shields.io/badge/status-research%20prototype-f0ad4e)
![License](https://img.shields.io/badge/code-Apache--2.0-2f81f7)
![Result](https://img.shields.io/badge/final%20latency-not%20established-6e7681)

`cat facial timing` · `temporal ML` · `CatFACS / landmarks` · `SHA-256 provenance`

</div>

## Abstract

**Fast-CAT-SHAiTan** is an experimental, reproducible pipeline for measuring how quickly one cat produces a facial movement corresponding to a facial movement produced by another cat.

The primary quantity is a latency in milliseconds:

```text
latency_ms = (t_responder - t_signaller) * 1000
```

For rapid facial mimicry we initially use the conventional search window `0 <= latency <= 1000 ms`, then estimate the observed latency distribution instead of treating one second as the answer.

The project uses public or otherwise lawfully accessible source material, AI-assisted temporal detection, explicit uncertainty, and SHA-256-bound experiment records. **No final biological estimate is claimed yet.**

The name is a small tribute to **Shaitan**, the cat who inspired the project; `SHA` in `SHAiTan` also reflects the provenance layer.

## Research question

Given two tracked cats and a facial action `a`, identify:

```text
(signaller, a, t0) -> (responder, a, t1)
```

and measure:

```text
Δt = t1 - t0
```

The goal is to estimate distributions of `Δt` by facial action, interaction context, source quality, and model confidence — not merely to classify an event as occurring "within one second".

## Current status

| Component | Status |
| --- | --- |
| Repository / Apache-2.0 code license | established |
| Open-video source catalogue | started |
| Cryptographic result schema | started |
| Published-sequence replay | **PILOT_000 complete** |
| Raw-video facial-event detector | not yet validated |
| Independent frame-level latency estimate | not established |
| Population-level feline reaction time | **not established** |

Machine-readable status: [`PROJECT_STATUS.json`](PROJECT_STATUS.json)

## PILOT_000 — published timestamp replay

The first reproducibility check replays the example event sequence published in:

> Martvel G. et al. (2024), *Computational investigation of the social function of domestic cat facial signals*, Scientific Reports.

Paper: https://doi.org/10.1038/s41598-024-79216-2  
Reference implementation: https://github.com/teddy4445/social_function_of_domestic_facial_signals

For the matching signaller → responder actions present in the published example sequence:

| action | signaller | responder | latency |
| --- | ---: | ---: | ---: |
| AU25 | 0.00 s | 0.30 s | **300 ms** |
| AU26 | 0.30 s | 0.45 s | **150 ms** |
| EAD104 | 1.00 s | 1.15 s | **150 ms** |

Pilot summary:

```text
N_MATCHES = 3
MIN_MS    = 150
MEDIAN_MS = 150
MEAN_MS   = 200
MAX_MS    = 300
```

**Interpretation boundary:** these three values come from an example sequence in the paper. They are useful for testing our timing/replay machinery, but they are **not** an independent estimate of "the reaction time of cats" and must not be presented as one.

Replay:

```bash
python scripts/replay_pilot_000.py
```

Frozen record: [`experiments/pilot_000/pilot_000.json`](experiments/pilot_000/pilot_000.json)

## Why we need a new experiment

The 2024 study defines rapid facial mimicry within a **1-second window** and reports a source dataset of 184 videos recorded at 60 fps. The raw dataset is available from the authors upon reasonable request rather than bundled with the public code repository.

At 60 fps, one frame is approximately:

```text
1000 / 60 = 16.67 ms
```

That is fine enough to ask a more precise question: where inside the 0–1000 ms window do matched responses actually occur?

## Open raw-video candidates

We do **not** treat random internet clips as ground truth. They are candidate material for detector development, false-positive testing, and later manually reviewed timing measurements.

The initial catalogue contains openly licensed Wikimedia Commons footage of two-cat interactions, including affiliative/play and non-affiliative/conflict contexts:

- `Kittys.webm` — two cats — CC BY-SA 4.0
- `Two cats holding each other and hugging.webm` — mutual contact/grooming — CC BY-SA 4.0
- `Play fight between cats.webmhd.webm` — two 14-week-old littermates play fighting — CC BY-SA 3.0
- `Tomcats conflict.webm` — two tomcats in conflict — CC0 1.0

Source metadata and stable source pages: [`data/open_video_sources.json`](data/open_video_sources.json)

Raw third-party media is not automatically relicensed by this repository and should not be committed without preserving its original licence and attribution requirements.

## Proposed measurement pipeline

```text
public video
    ↓
source URL + source licence + media hash
    ↓
cat detection / stable cat IDs
    ↓
face crop + 48 feline landmarks / CatFACS-compatible features
    ↓
temporal facial-action event detector
    ↓
(signaller action, responder matching action)
    ↓
frame-accurate Δt in milliseconds
    ↓
confidence + uncertainty + reviewer decision
    ↓
SHA-256-bound result record
```

### Timing rule

For each signaller event, candidate matches must satisfy:

```text
same_action = true
responder != signaller
0 <= t_responder - t_signaller <= 1.0 s
```

A later validated protocol will specify collision handling, repeated actions, simultaneous events, occlusion, dropped frames, variable-frame-rate video, and minimum detector confidence before any aggregate claim is admitted.

## Model direction

An existing **CatGPT** prototype from the JANUS working set is relevant as a baseline. It already represents cat state with features including ear positions, head/body variables and context; learns autoregressive transitions and n-grams; tracks motion statistics; maintains a reinforced `Slime Trace`; and checkpoints state to JSON.

Important: that CatGPT implementation is **not a Transformer**. It is a compact statistical autoregressive model. That makes it useful as an interpretable baseline, while a dedicated temporal attention/Transformer model can be evaluated separately for frame sequences.

See [`docs/MODEL_SELECTION.md`](docs/MODEL_SELECTION.md).

## Cryptographic provenance

SHA-256 is used here for **integrity and lineage**, not as a biological feature.

Each admitted experiment should bind at least:

```text
source_page
source_media_url
source_license
raw_media_sha256
video_stream_metadata
frame_selection_policy
model_id
model_weights_sha256
code_commit
configuration_sha256
event_table_sha256
result_sha256
```

This allows another reviewer to determine whether a reported result came from exactly the same media, model, code, and configuration.

## Scientific boundaries

This repository does not currently claim:

- a universal feline reaction time;
- that every matched facial movement is intentional communication;
- that temporal correlation alone proves mimicry or empathy;
- that an AI detector is equivalent to expert CatFACS annotation;
- that a low-resolution or unknown-frame-rate internet clip can support millisecond precision beyond its acquisition limits.

Negative and inconclusive results are valid outcomes.

## Related work

- Martvel G. et al., *Computational investigation of the social function of domestic cat facial signals* — https://doi.org/10.1038/s41598-024-79216-2
- Authors' code — https://github.com/teddy4445/social_function_of_domestic_facial_signals
- Martvel G. et al., *CatFLW: Cat Facial Landmarks in the Wild Dataset* — https://arxiv.org/abs/2305.04232

## Repository layout

```text
data/                       source manifests; no implied media relicensing
docs/                       protocol and model notes
experiments/                frozen pilot/result records
scripts/                    deterministic replay and analysis tools
PROJECT_STATUS.json         machine-readable maturity / claim ceiling
LICENSE                     Apache License 2.0 for repository-authored code
NOTICE                      attribution and third-party boundary
```

## License

Repository-authored code and documentation are licensed under **Apache License 2.0** unless a file states otherwise.

Third-party datasets, papers, code, models, and media retain their own licences and terms. References to them do not place those works under Apache-2.0.
