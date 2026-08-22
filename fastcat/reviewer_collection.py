from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastcat.review_consensus import build_consensus_report, canonical_sha256


ATTESTATION_SCHEMA = "Fast-CAT/PILOT-001/reviewer-attestation/v1.0"
COLLECTION_SCHEMA = "Fast-CAT/PILOT-001/reviewer-collection/v1.0"
# Trust anchor is intentionally outside caller-supplied collection/submission
# protocol objects. Changing it requires a reviewed source-code change.
FROZEN_SUBMISSION_PROTOCOL_CANONICAL_SHA256 = (
    "645db2a129c42d5220cd34e9f7da81366e446ddf524be9ad47e6687690a92cac"
)


def _prefixed(index: int, code: str) -> str:
    return f"REVIEW_{index}:{code}"


def _validate_attestation_semantics(
    *,
    attestation: dict[str, Any],
    analysis: dict[str, Any],
    verifier: dict[str, Any],
    submission_protocol: dict[str, Any],
    index: int,
) -> list[str]:
    failures: list[str] = []
    expected = submission_protocol.get("expected_blinded_package", {})

    if attestation.get("schema") != ATTESTATION_SCHEMA:
        failures.append(_prefixed(index, "ATTESTATION_SCHEMA_MISMATCH"))
    if not str(attestation.get("reviewer_id", "")).strip():
        failures.append(_prefixed(index, "REVIEWER_ID_MISSING"))
    if attestation.get("independent_of_fastcat_model_evidence_before_label_freeze") is not True:
        failures.append(_prefixed(index, "ATTESTATION_INDEPENDENCE_NOT_CONFIRMED"))
    if attestation.get("saw_landmark_or_motion_rankings_before_label_freeze") is not False:
        failures.append(_prefixed(index, "ATTESTATION_MODEL_RANKING_EXPOSURE_NOT_FALSE"))
    if attestation.get("labels_frozen_before_model_reveal") is not True:
        failures.append(_prefixed(index, "ATTESTATION_LABEL_FREEZE_NOT_CONFIRMED"))
    if not str(attestation.get("catfacs_competence_basis", "")).strip():
        failures.append(_prefixed(index, "ATTESTATION_CATFACS_COMPETENCE_BASIS_MISSING"))
    if not str(attestation.get("review_completed_utc", "")).strip():
        failures.append(_prefixed(index, "ATTESTATION_REVIEW_COMPLETED_UTC_MISSING"))

    analysis_form_sha = str(analysis.get("completed_review_form_sha256", ""))
    attestation_form_sha = str(attestation.get("completed_review_form_sha256", ""))
    verifier_form_sha = str(verifier.get("review_form_sha256", ""))
    if not analysis_form_sha:
        failures.append(_prefixed(index, "ANALYSIS_REVIEW_FORM_SHA256_MISSING"))
    if attestation_form_sha != analysis_form_sha:
        failures.append(_prefixed(index, "ATTESTATION_REVIEW_FORM_SHA256_MISMATCH"))
    if verifier_form_sha != analysis_form_sha:
        failures.append(_prefixed(index, "VERIFIER_REVIEW_FORM_SHA256_MISMATCH"))

    expected_source = str(submission_protocol.get("source_id", ""))
    if str(analysis.get("source_id", "")) != expected_source:
        failures.append(_prefixed(index, "ANALYSIS_SOURCE_NOT_SUBMISSION_PROTOCOL_SOURCE"))

    expected_manifest_sha = str(expected.get("frame_manifest_file_sha256", ""))
    if str(analysis.get("frame_manifest_file_sha256", "")) != expected_manifest_sha:
        failures.append(_prefixed(index, "ANALYSIS_FRAME_MANIFEST_NOT_FROZEN_PACKAGE"))
    if str(verifier.get("frame_manifest_file_sha256", "")) != expected_manifest_sha:
        failures.append(_prefixed(index, "VERIFIER_FRAME_MANIFEST_NOT_FROZEN_PACKAGE"))

    if str(attestation.get("blinded_package_artifact_digest", "")) != str(
        expected.get("workflow_artifact_digest", "")
    ):
        failures.append(_prefixed(index, "ATTESTATION_PACKAGE_DIGEST_MISMATCH"))
    if str(attestation.get("blank_review_form_sha256", "")) != str(
        expected.get("blank_review_form_sha256", "")
    ):
        failures.append(_prefixed(index, "ATTESTATION_BLANK_FORM_SHA256_MISMATCH"))

    if canonical_sha256(attestation) != analysis.get("reviewer_attestation_sha256"):
        failures.append(_prefixed(index, "ATTESTATION_CANONICAL_SHA256_MISMATCH"))
    return failures


def _validate_analysis_row_shapes(analysis: dict[str, Any], index: int) -> list[str]:
    """Reject malformed external row containers before consensus code touches them."""
    rows = analysis.get("normalized_review_rows")
    if rows is None:
        return []
    if not isinstance(rows, list):
        return [_prefixed(index, "NORMALIZED_REVIEW_ROWS_NOT_LIST")]
    failures: list[str] = []
    for row_index, row in enumerate(rows):
        if not isinstance(row, dict):
            failures.append(
                _prefixed(index, f"NORMALIZED_REVIEW_ROW_{row_index}_NOT_OBJECT")
            )
    return failures


def _validate_bundle_through_consensus_core(
    *, bundle: dict[str, Any], policy: dict[str, Any], index: int
) -> list[str]:
    single_policy = deepcopy(policy)
    single_policy["required_reviewers"] = 1
    try:
        probe = build_consensus_report(bundles=[bundle], policy=single_policy)
    except Exception as exc:
        return [
            _prefixed(index, f"CONSENSUS_CORE_REPLAY_EXCEPTION_{type(exc).__name__}")
        ]
    if probe.get("status") == "PASS":
        return []
    failures: list[str] = []
    for failure in probe.get("failures", []):
        text = str(failure)
        if text.startswith("REVIEW_0:"):
            text = f"REVIEW_{index}:" + text[len("REVIEW_0:") :]
        failures.append(text)
    return failures


def build_reviewer_collection_receipt(
    *,
    bundles: list[dict[str, Any]],
    collection_policy: dict[str, Any],
    submission_protocol: dict[str, Any],
    consensus_policy: dict[str, Any],
) -> dict[str, Any]:
    """Validate a collection of blinded reviewer bundles before consensus.

    The exact submission-protocol identity is anchored in this source module,
    not in caller-controlled policy JSON. The policy copy must agree with the
    source-controlled anchor, but cannot redefine it.
    """

    failures: list[str] = []
    required = int(collection_policy.get("required_reviewers", 2))
    if required < 2:
        failures.append("COLLECTION_POLICY_REQUIRED_REVIEWERS_BELOW_TWO")

    expected_submission_schema = str(
        collection_policy.get("submission_protocol_schema", "")
    )
    if submission_protocol.get("schema") != expected_submission_schema:
        failures.append("SUBMISSION_PROTOCOL_SCHEMA_MISMATCH")

    policy_submission_sha = str(
        collection_policy.get("submission_protocol_canonical_sha256", "")
    )
    actual_submission_sha = canonical_sha256(submission_protocol)
    if not policy_submission_sha:
        failures.append("SUBMISSION_PROTOCOL_CANONICAL_SHA256_NOT_PINNED")
    elif policy_submission_sha != FROZEN_SUBMISSION_PROTOCOL_CANONICAL_SHA256:
        failures.append("COLLECTION_POLICY_SUBMISSION_PROTOCOL_PIN_NOT_TRUSTED")
    if actual_submission_sha != FROZEN_SUBMISSION_PROTOCOL_CANONICAL_SHA256:
        failures.append("SUBMISSION_PROTOCOL_CANONICAL_SHA256_MISMATCH")

    expected_consensus_schema = str(collection_policy.get("consensus_policy_schema", ""))
    if consensus_policy.get("schema") != expected_consensus_schema:
        failures.append("CONSENSUS_POLICY_SCHEMA_MISMATCH")
    if int(consensus_policy.get("required_reviewers", -1)) != required:
        failures.append("COLLECTION_AND_CONSENSUS_REVIEWER_COUNT_MISMATCH")

    bundle_receipts: list[dict[str, Any]] = []
    for index, bundle in enumerate(bundles):
        bundle_failures: list[str] = []
        if not isinstance(bundle, dict):
            bundle_failures.append(_prefixed(index, "BUNDLE_NOT_OBJECT"))
            analysis: dict[str, Any] = {}
            attestation: dict[str, Any] = {}
            verifier: dict[str, Any] = {}
        else:
            analysis = bundle.get("analysis") if isinstance(bundle.get("analysis"), dict) else {}
            attestation = (
                bundle.get("attestation") if isinstance(bundle.get("attestation"), dict) else {}
            )
            verifier = bundle.get("verifier") if isinstance(bundle.get("verifier"), dict) else {}
            if not analysis:
                bundle_failures.append(_prefixed(index, "ANALYSIS_REPORT_MISSING"))
            if not attestation:
                bundle_failures.append(_prefixed(index, "ATTESTATION_MISSING"))
            if not verifier:
                bundle_failures.append(_prefixed(index, "VERIFIER_REPORT_MISSING"))

        if not bundle_failures:
            bundle_failures.extend(_validate_analysis_row_shapes(analysis, index))
            bundle_failures.extend(
                _validate_attestation_semantics(
                    attestation=attestation,
                    analysis=analysis,
                    verifier=verifier,
                    submission_protocol=submission_protocol,
                    index=index,
                )
            )
            if not bundle_failures:
                bundle_failures.extend(
                    _validate_bundle_through_consensus_core(
                        bundle=bundle,
                        policy=consensus_policy,
                        index=index,
                    )
                )

        reviewer_id = str(attestation.get("reviewer_id", "")).strip()
        bundle_receipts.append(
            {
                "bundle_index": index,
                "admissible": not bundle_failures,
                "failures": sorted(set(bundle_failures)),
                "reviewer_id": reviewer_id or None,
                "reviewer_attestation_sha256": (
                    canonical_sha256(attestation) if attestation else None
                ),
                "completed_review_form_sha256": analysis.get(
                    "completed_review_form_sha256"
                ),
                "analysis_report_sha256": canonical_sha256(analysis) if analysis else None,
                "verifier_report_sha256": canonical_sha256(verifier) if verifier else None,
                "frame_manifest_file_sha256": analysis.get(
                    "frame_manifest_file_sha256"
                ),
                "reviewer_declared_independence": attestation.get(
                    "independent_of_fastcat_model_evidence_before_label_freeze"
                ),
                "reviewer_declared_model_ranking_exposure": attestation.get(
                    "saw_landmark_or_motion_rankings_before_label_freeze"
                ),
                "reviewer_declared_labels_frozen_before_model_reveal": attestation.get(
                    "labels_frozen_before_model_reveal"
                ),
            }
        )
        failures.extend(bundle_failures)

    admissible = [receipt for receipt in bundle_receipts if receipt["admissible"]]
    reviewer_ids = [str(receipt["reviewer_id"]) for receipt in admissible]
    attestation_hashes = [
        str(receipt["reviewer_attestation_sha256"]) for receipt in admissible
    ]
    completed_form_hashes = [
        str(receipt["completed_review_form_sha256"]) for receipt in admissible
    ]

    if len(set(reviewer_ids)) != len(reviewer_ids):
        failures.append("REVIEWER_IDS_NOT_DISTINCT")
    if len(set(attestation_hashes)) != len(attestation_hashes):
        failures.append("ATTESTATION_HASHES_NOT_DISTINCT")

    full_consensus_probe: dict[str, Any] | None = None
    if not failures and len(admissible) >= required:
        try:
            full_consensus_probe = build_consensus_report(
                bundles=bundles,
                policy=consensus_policy,
            )
        except Exception as exc:
            failures.append(f"CONSENSUS_CORE_EXCEPTION_{type(exc).__name__}")
        else:
            if full_consensus_probe.get("status") != "PASS":
                failures.extend(str(x) for x in full_consensus_probe.get("failures", []))

    failures = sorted(set(failures))
    if failures:
        state = "INVALID_COLLECTION"
        status = "FAIL"
        ready = False
    elif len(admissible) == 0:
        state = "WAITING_FOR_FIRST_REVIEWER"
        status = "PASS"
        ready = False
    elif len(admissible) < required:
        state = "WAITING_FOR_SECOND_REVIEWER"
        status = "PASS"
        ready = False
    else:
        state = "READY_FOR_CONSENSUS"
        status = "PASS"
        ready = True

    collision_count = len(completed_form_hashes) - len(set(completed_form_hashes))
    return {
        "schema": COLLECTION_SCHEMA,
        "status": status,
        "collection_state": state,
        "failures": failures,
        "required_reviewers": required,
        "submitted_bundle_count": len(bundles),
        "admissible_bundle_count": len(admissible),
        "bundle_receipts": bundle_receipts,
        "submission_protocol_canonical_sha256": actual_submission_sha,
        "trusted_submission_protocol_canonical_sha256": FROZEN_SUBMISSION_PROTOCOL_CANONICAL_SHA256,
        "submission_protocol_identity_matches_frozen_policy": (
            actual_submission_sha == FROZEN_SUBMISSION_PROTOCOL_CANONICAL_SHA256
            and policy_submission_sha == FROZEN_SUBMISSION_PROTOCOL_CANONICAL_SHA256
        ),
        "reviewer_ids": reviewer_ids,
        "reviewer_attestation_sha256s": attestation_hashes,
        "completed_review_form_sha256s": completed_form_hashes,
        "completed_review_form_hash_collision_count": collision_count,
        "completed_review_forms_must_be_distinct": False,
        "consensus_admission_ready": ready,
        "consensus_core_preflight_status": (
            full_consensus_probe.get("status") if full_consensus_probe else None
        ),
        "human_independence_proven_by_software": False,
        "reviewer_independence_semantics": "Software verifies reviewer-declared independence fields, exact package lineage, distinct reviewer identifiers and distinct attestation identities. It does not prove personhood, institutional independence, competence truthfulness or absence of off-channel collusion.",
        "independent_frame_level_estimate_established": False,
        "claim_ceiling": "Reviewer collection admission establishes only artifact readiness for the frozen multi-reviewer consensus gate. Waiting states are not failures; invalid bundles fail closed. No collection receipt by itself establishes EAD onset, mimicry, latency, population-level feline behavior, or INDEPENDENT_FRAME_LEVEL_ESTIMATE.",
    }
