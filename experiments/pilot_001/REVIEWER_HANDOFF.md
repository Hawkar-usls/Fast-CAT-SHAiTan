# PILOT_001 — Independent Blinded Reviewer Handoff

This handoff is for a **real external reviewer** completing the frozen model-blinded PILOT_001 EAD103/EAD104 frame review.

The review is intentionally separated from Fast-CAT model-derived landmark, motion, ranking, onset, pairing, and latency evidence until the reviewer has completed and frozen their labels.

## 1. Obtain a project-provided blinded-package transport

The outer ZIP file is a transport container. Different verified mirrors or repacked ZIPs may have different outer SHA-256 values.

The scientific input is the exact canonical content identified by:

- content identity file SHA-256: `87877d69e5fcfd44433b93106740ef641c320a8037b06aefe281fff9179378fd`
- package manifest SHA-256: `85bf6a190377a304b607bd611cd7d9476e521b98682286f4d9cfb47d5878e3e4`
- manifest files-payload SHA-256: `2a550d1d32fff07757c6838f224a63fa5d87a00017b4dcc110154bd75fd99513`
- frame manifest SHA-256: `0271018446726ccabd3be78e29c426e03d772e2bc01bb40ceb32ff246ae51c67`
- blank review form SHA-256: `b464040c69491ac1ce7e1083f2745a85361fe3884cce1b37d6c9c7bae946622d`

The original GitHub Actions artifact is preserved as origin provenance, but its outer ZIP digest is **not** the long-term admission authority.

## 2. Verify the package before reviewing

From a Fast-CAT checkout containing the current PILOT_001 protocols, run:

```bash
python scripts/verify_blinded_package_content.py \
  --identity experiments/pilot_001/blinded_review_content_identity.json \
  --zip /path/to/received-package.zip \
  --out package-verification.json
```

Proceed only if the receipt reports:

```text
status = EXACT_CANONICAL_CONTENT_MATCH
verified_payload_files = 53
```

A different outer ZIP SHA-256 is acceptable only when the canonical package content verifies exactly. Any missing, modified, duplicated, injected, or unexpected file inside the reviewer package invalidates that transport.

Record the SHA-256 of the actual ZIP received if desired; it is transport provenance, not the scientific package identity.

## 3. Do not inspect Fast-CAT model evidence before label freeze

Before freezing the completed review CSV, do **not** inspect or receive:

- landmark coordinates or overlays;
- ear-motion rankings or scores;
- candidate onset times;
- pairings or latency estimates;
- model-selected “interesting” frames;
- any other Fast-CAT model-derived evidence that could bias the blinded labels.

If such exposure occurred before label freeze, the attestation must say so and the submission will fail closed.

## 4. Follow the immutable package instructions

Open the verified package and read:

`package/REVIEW_INSTRUCTIONS.md`

Do not modify the package instructions, frame manifest, PNG frames, package manifest, or blank-form lineage.

Complete the review form for all **100 required rows** (50 decoded frames × 2 subjects) using only the permitted states and identity fields defined by the frozen review protocol.

A valid independent review is allowed to contain:

- no visible EAD events;
- no matched response pairs;
- `UNCERTAIN` states;
- `NOT_VISIBLE` states;
- disagreements with another reviewer.

Fast-CAT must preserve those outcomes rather than infer or repair labels.

## 5. Freeze the completed CSV before any model reveal

After finishing all labels, compute the exact SHA-256 of the completed CSV bytes.

Examples:

```bash
sha256sum completed_review.csv
```

or on PowerShell:

```powershell
(Get-FileHash .\completed_review.csv -Algorithm SHA256).Hash.ToLower()
```

Do this **before** viewing Fast-CAT model-derived evidence.

Do not edit the completed CSV after recording this hash. If a correction is scientifically necessary, create a new explicitly identified submission rather than silently changing frozen bytes.

## 6. Fill reviewer attestation v1.1

Copy:

`experiments/pilot_001/reviewer_attestation.template.json`

Fill the reviewer-specific fields only after the CSV is frozen.

Required declarations include:

- a non-empty pseudonymous or institutional `reviewer_id`;
- independent-of-model-evidence declaration;
- no pre-freeze landmark/motion-ranking exposure;
- labels frozen before model reveal;
- a non-empty CatFACS competence basis;
- exact completed CSV SHA-256;
- review completion timestamp.

The canonical package identity hashes are already frozen in the template and must not be changed.

`blinded_package_transport_sha256` is optional. If supplied, it should be the SHA-256 of the actual ZIP/mirror received. Different reviewers may legitimately have different transport hashes while reviewing the same exact canonical content.

Software verifies the submitted declaration and artifact consistency. It **cannot** prove reviewer personhood, competence truthfulness, institutional independence, absence of undisclosed exposure, or absence of off-channel collusion.

## 7. Submit the frozen reviewer bundle

Provide:

1. the completed review CSV;
2. the exact `package/frame_manifest.json` from the verified blinded package;
3. the completed reviewer attestation JSON;
4. preferably the `package-verification.json` receipt for audit provenance.

Do not include model rankings, landmark outputs, or a post-hoc edited package.

Fast-CAT will then perform:

```text
canonical package binding
→ review ingestion
→ independent verifier replay
→ reviewer collection admission
```

One admissible real reviewer produces:

`WAITING_FOR_SECOND_REVIEWER`

It does **not** produce a biological latency result.

## 8. Second reviewer repeats independently

The second reviewer must independently receive and verify the canonical blinded content, complete their labels, freeze their CSV, and submit their own attestation.

Only after at least two admissible distinct reviewer bundles exist can the collection state become:

`READY_FOR_CONSENSUS`

The downstream consensus gate preserves reviewer disagreement as `DISAGREEMENT`; it does not guess an answer.

## Claim ceiling

This handoff and its verification machinery establish reviewer-package provenance and a fail-closed route for receiving independent blinded labels. They do not themselves establish subject identity, CatFACS correctness, EAD103/EAD104 onset truth, mimicry, delta-t, feline response latency, population-level behavior, or `INDEPENDENT_FRAME_LEVEL_ESTIMATE`.
