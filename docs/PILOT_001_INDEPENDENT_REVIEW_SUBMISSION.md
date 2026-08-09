# PILOT_001 independent review submission

This gate begins **after** an eligible reviewer has completed the frozen model-blinded review package.

It does not ask Fast-CAT, CatGPT, the landmark backend, or the current model-assisted development session to invent action labels.

## Required input

Use the exact blinded package bound in [`experiments/pilot_001/independent_review_submission_protocol.json`](../experiments/pilot_001/independent_review_submission_protocol.json).

The frozen package is identified by its GitHub Actions artifact digest plus byte-level SHA-256 identities for the blank review form, frame manifest, package manifest and review instructions. The submission protocol also preserves the producing Fast-CAT head/tree, workflow run/artifact IDs, raw-media SHA-256 and decoded-PTS identity.

The reviewer completes all 100 rows of `review_form.csv`:

- `identity_confirmed`: `yes`, `no`, or `uncertain`;
- each EAD103/EAD104 ear field: `ABSENT`, `PRESENT`, `UNCERTAIN`, or `NOT_VISIBLE`;
- optional free-text review notes.

No model score, landmark field, predicted action, or ranking column may be added.

After the CSV is complete, compute its SHA-256 **before** revealing any Fast-CAT landmark/motion ranking to that reviewer. Then complete a copy of [`reviewer_attestation.template.json`](../experiments/pilot_001/reviewer_attestation.template.json).

In addition to the completed-form hash, the reviewer attestation must copy these two identifiers from the frozen submission protocol:

```text
blinded_package_artifact_digest
blank_review_form_sha256
```

Those fields prevent a completed CSV from being silently paired with a different starting package or blank-form lineage.

The attestation is evidence of a declaration, not magical proof of reviewer identity or expertise. Reviewer identity/competence must be documented honestly; software only checks the declared fields and cryptographic lineage.

## Ingestion

```bash
python scripts/ingest_independent_action_review.py \
  --protocol experiments/pilot_001/independent_review_submission_protocol.json \
  --frame-manifest /path/to/blinded-package/frame_manifest.json \
  --review-form /path/to/completed_review_form.csv \
  --attestation /path/to/reviewer_attestation.json \
  --out artifacts/pilot_001_independent_review.json
```

The production command first validates the **exact frozen-package binding**. If the frame-manifest file SHA-256, GitHub Actions artifact digest, or blank-form SHA-256 does not match the frozen package, ingestion fails before any submitted label can become an onset or matched event.

A valid submission is tied to:

```text
frozen GitHub Actions package digest
+ exact blank-form SHA-256
+ exact frame-manifest SHA-256
+ raw media SHA-256
+ decoded-frame PTS SHA-256
+ completed CSV SHA-256
+ reviewer attestation SHA-256
```

## Onset rule

For each subject, action and ear laterality, Fast-CAT derives an onset only for an **immediately adjacent** decoded-frame transition:

```text
previous frame = ABSENT
current frame  = PRESENT
identity confirmed = yes on both frames
```

`UNCERTAIN`, `NOT_VISIBLE`, identity `no`, or identity `uncertain` cannot bridge an onset.

The event records both decoded PTS values:

```text
(previous_absent_pts_s, onset_pts_s]
```

No header-FPS timestamp is substituted.

## Pairing and latency interval

For each onset, the frozen matcher searches the other subject for the earliest unused onset with the same action code inside the 0–1000 ms **point-estimate** window. Signaller and responder ear laterality remain explicit even though matching is by action code.

For signaller bracket `(s_prev, s]` and responder bracket `(r_prev, r]`:

```text
point_ms = (r - s) * 1000
lower_ms = (r_prev - s) * 1000
upper_ms = (r - s_prev) * 1000
```

An interval that crosses 0 or 1000 ms is preserved and marked boundary-ambiguous rather than silently rounded into certainty.

## Independent replay

```bash
python scripts/verify_independent_action_review.py \
  --protocol experiments/pilot_001/independent_review_submission_protocol.json \
  --frame-manifest /path/to/blinded-package/frame_manifest.json \
  --review-form /path/to/completed_review_form.csv \
  --attestation /path/to/reviewer_attestation.json \
  --analysis-report artifacts/pilot_001_independent_review.json \
  --out artifacts/pilot_001_independent_review_verifier.json
```

The verifier does not import the review-ingestion analysis module. It independently checks frozen package lineage, re-parses the CSV, recomputes the onset table and deterministic pairing, then compares content hashes with the analysis report.

## Negative outcomes

These are valid and must remain publishable:

```text
0 admitted onsets
0 matched action pairs
all candidate regions UNCERTAIN / NOT_VISIBLE
identity continuity insufficient for admission
```

A zero-event or zero-match review is not a failed experiment.

## Claim boundary

A successful ingestion may establish that an independent blinded review submission is internally consistent, bound to the frozen review input, and that its onset/pairing tables replay deterministically.

It **does not automatically set**:

```text
INDEPENDENT_FRAME_LEVEL_ESTIMATE = ESTABLISHED
```

The final PILOT_001 admission still has to satisfy the complete protocol claim gate, including independently adequate subject identity and admissible landmark/manual geometry evidence. Causal mimicry, intentional communication, and population-level feline reaction time are outside this ingestion gate.
