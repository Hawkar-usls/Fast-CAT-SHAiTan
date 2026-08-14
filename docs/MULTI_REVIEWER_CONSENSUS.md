# PILOT_001 multi-reviewer consensus gate

Fast-CAT now has a preregistered software boundary for combining more than one genuinely independent blinded action review without turning disagreement into invented biological evidence.

## Why this gate exists

The existing PILOT_001 ingestion path can bind one completed EAD103/EAD104 review to the exact frozen blinded frame package, replay the review deterministically, and preserve zero-event or zero-match outcomes. A single independent reviewer is still vulnerable to ordinary annotation uncertainty. The next software boundary therefore separates three questions:

1. Did each reviewer independently label the exact same frozen package?
2. Do the reviewer state tables agree at the exact frame/state level?
3. Which action onsets remain derivable when disagreement is preserved instead of averaged away?

The gate answers those questions only. It does not create labels, infer reviewer competence, validate CatFLW landmarks, prove causal mimicry, or establish a population-level feline reaction time.

## Required reviewer bundle

Each reviewer contributes three artifacts:

- the exact reviewer attestation;
- the bound ingestion analysis report;
- the independent verifier report for that ingestion.

Before cross-review comparison, the consensus implementation checks that the analysis passed, exact frozen-package binding was established, the independent verifier passed, the attestation canonical SHA-256 matches the analysis, normalized rows re-hash correctly, and the onset/matching results can be re-derived from those rows.

The reviewer identifiers and attestation hashes must be distinct. Reviewers must also be bound to the same source, frame manifest, PTS values and row-key sequence.

## Consensus rule

Version 1.0 deliberately uses the strictest simple rule: exact unanimity.

For each frame/subject cell, the following states are compared separately:

- `identity_confirmed`;
- `left_ear_EAD103`;
- `right_ear_EAD103`;
- `left_ear_EAD104`;
- `right_ear_EAD104`.

If all reviewers supplied the same state, that state is preserved. Any non-unanimous cell becomes `DISAGREEMENT`.

`DISAGREEMENT` is neither dropped nor converted to a majority label. There is no adjudication step in v1.0.

## Event admission

A consensus action onset exists only when all of the following hold:

- subject identity is unanimously `yes` on the previous and current frame;
- the previous consensus state is exactly `ABSENT`;
- the current consensus state is exactly `PRESENT`;
- the two rows are adjacent decoded frames.

`DISAGREEMENT`, `UNCERTAIN`, and `NOT_VISIBLE` never bridge an onset.

The event time remains decoded-frame PTS. Matching remains deterministic, cross-subject, same-action, earliest-unused-response, with the frozen 1000 ms point-estimate window and both local acquisition brackets retained.

## Agreement output

The v1.0 gate reports the exact state agreement rate, unanimous cell count, disagreement cell count and per-field counts. It intentionally does not require Cohen/Fleiss kappa at this stage: the pilot is small and highly prevalence-sensitive, so the raw audit quantity is kept separate from inferential interpretation.

## Negative outcomes

All of these are valid outcomes:

- two valid reviews with perfect agreement but zero onsets;
- two valid reviews with onsets but zero matched cross-cat responses;
- valid reviews containing disagreements that block some or all consensus onsets.

The gate must never convert any of them into a positive latency result.

## Current evidence status

The software boundary and synthetic CI fixtures can be tested now. No real two-reviewer biological bundle is present in the repository at the time this protocol is introduced.

Therefore:

```text
MULTI_REVIEWER_CONSENSUS_SOFTWARE_GATE   ESTABLISHED_BY_TESTS/CI
REAL_MULTI_REVIEWER_SUBMISSIONS          NOT_RECEIVED
BIOLOGICAL_CONSENSUS_ONSETS              NOT_ESTABLISHED
BIOLOGICAL_CONSENSUS_DELTA_T              NOT_ESTABLISHED
INDEPENDENT_FRAME_LEVEL_ESTIMATE          NOT_ESTABLISHED
```

Synthetic CI reviewers are software fixtures only and must never be cited as feline evidence.

## Command-line use

After two real reviewer bundles independently pass the existing ingestion + verifier gates:

```bash
python scripts/build_multi_reviewer_consensus.py \
  --analysis reviewer_A_analysis.json \
  --attestation reviewer_A_attestation.json \
  --verifier reviewer_A_verifier.json \
  --analysis reviewer_B_analysis.json \
  --attestation reviewer_B_attestation.json \
  --verifier reviewer_B_verifier.json \
  --out reviewer_consensus.json
```

The implementation is fail-closed: any broken lineage, verifier mismatch, reviewer identity collision, row misalignment or replay mismatch prevents consensus-event derivation.

## Claim ceiling

A successful future run may establish a multi-reviewer unanimous frame-state table and deterministic onset/matching replay in review scope. It still does not by itself establish landmark accuracy, independent subject identity outside reviewer scope, population-level feline latency, causal mimicry, intentional communication, or `INDEPENDENT_FRAME_LEVEL_ESTIMATE`.
