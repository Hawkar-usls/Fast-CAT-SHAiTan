from __future__ import annotations

from typing import Any

from fastcat.review_ingestion import (
    canonical_sha256,
    derive_onsets,
    deterministic_pairing,
    summarize_matches,
    validate_frame_manifest,
    validate_review_rows,
)
from fastcat.review_submission_binding import validate_frozen_package_binding


ATTESTATION_SCHEMA = "Fast-CAT/PILOT-001/reviewer-attestation/v1.1"
REPORT_SCHEMA = "Fast-CAT/PILOT-001/independent-review-ingestion/v1.2"


def _validate_attestation(
    *, attestation: dict[str, Any], completed_review_form_sha256: str
) -> list[str]:
    failures: list[str] = []
    if attestation.get("schema") != ATTESTATION_SCHEMA:
        failures.append("ATTESTATION_SCHEMA_MISMATCH")
    if not str(attestation.get("reviewer_id", "")).strip():
        failures.append("ATTESTATION_REVIEWER_ID_MISSING")
    if attestation.get("independent_of_fastcat_model_evidence_before_label_freeze") is not True:
        failures.append("ATTESTATION_INDEPENDENCE_NOT_CONFIRMED")
    if attestation.get("saw_landmark_or_motion_rankings_before_label_freeze") is not False:
        failures.append("ATTESTATION_MODEL_RANKING_EXPOSURE_NOT_FALSE")
    if attestation.get("labels_frozen_before_model_reveal") is not True:
        failures.append("ATTESTATION_LABEL_FREEZE_NOT_CONFIRMED")
    if not str(attestation.get("catfacs_competence_basis", "")).strip():
        failures.append("ATTESTATION_CATFACS_COMPETENCE_BASIS_MISSING")
    if not str(attestation.get("review_completed_utc", "")).strip():
        failures.append("ATTESTATION_REVIEW_COMPLETED_UTC_MISSING")
    if str(attestation.get("completed_review_form_sha256", "")) != completed_review_form_sha256:
        failures.append("ATTESTATION_REVIEW_FORM_SHA256_MISMATCH")
    transport = str(attestation.get("blinded_package_transport_sha256", "")).strip()
    if transport and (
        len(transport) != 64
        or any(c not in "0123456789abcdefABCDEF" for c in transport)
    ):
        failures.append("ATTESTATION_TRANSPORT_SHA256_INVALID")
    return failures


def _fail_closed_report(
    *,
    protocol: dict[str, Any],
    frame_manifest_file_sha256: str,
    attestation: dict[str, Any],
    completed_review_form_sha256: str,
    failures: list[str],
    package_binding_established: bool,
) -> dict[str, Any]:
    empty: list[dict[str, Any]] = []
    expected = protocol.get("expected_blinded_package", {})
    return {
        "schema": REPORT_SCHEMA,
        "status": "FAIL",
        "scientific_outcome": "INVALID_SUBMISSION",
        "failures": sorted(set(failures)),
        "source_id": protocol.get("source_id"),
        "completed_review_form_sha256": completed_review_form_sha256,
        "frame_manifest_file_sha256": frame_manifest_file_sha256,
        "reviewer_attestation_sha256": canonical_sha256(attestation),
        "blinded_package_content_identity_file_sha256": expected.get(
            "content_identity_file_sha256"
        ),
        "blinded_package_manifest_sha256": expected.get("package_manifest_file_sha256"),
        "blinded_package_files_payload_sha256": expected.get("files_payload_sha256"),
        "blinded_package_transport_sha256": attestation.get(
            "blinded_package_transport_sha256"
        )
        or None,
        "normalized_review_rows": [],
        "normalized_review_rows_sha256": None,
        "derived_onsets": [],
        "derived_onsets_sha256": canonical_sha256(empty),
        "matches": [],
        "matches_sha256": canonical_sha256(empty),
        "unmatched_signaller_event_ids": [],
        "summary": summarize_matches([]),
        "review_submission_integrity_established": False,
        "exact_frozen_package_binding_established": package_binding_established,
        "transport_independent_package_content_binding_established": package_binding_established,
        "independently_reviewed_action_onset_table_established_in_review_scope": False,
        "independent_frame_level_estimate_established": False,
        "claim_ceiling": "Submission failed closed. Canonical blinded-package content binding and reviewer-declared independence are necessary but do not by themselves establish a biological action, mimicry or latency result.",
    }


def build_bound_submission_report(
    *,
    protocol: dict[str, Any],
    frame_manifest: dict[str, Any],
    frame_manifest_file_sha256: str,
    headers: list[str],
    review_rows: list[dict[str, str]],
    attestation: dict[str, Any],
    completed_review_form_sha256: str,
) -> dict[str, Any]:
    """Production PILOT_001 v1.2 review-ingestion boundary.

    Scientific package identity is content-addressed. The original GitHub
    Actions ZIP remains origin provenance but is not the admission authority;
    a byte-distinct transport is admissible only when it contains the exact
    canonical blinded package bytes identified by the frozen content identity.
    """
    binding_failures = validate_frozen_package_binding(
        protocol=protocol,
        frame_manifest_file_sha256=frame_manifest_file_sha256,
        attestation=attestation,
    )
    if binding_failures:
        return _fail_closed_report(
            protocol=protocol,
            frame_manifest_file_sha256=frame_manifest_file_sha256,
            attestation=attestation,
            completed_review_form_sha256=completed_review_form_sha256,
            failures=binding_failures,
            package_binding_established=False,
        )

    failures: list[str] = []
    failures.extend(
        _validate_attestation(
            attestation=attestation,
            completed_review_form_sha256=completed_review_form_sha256,
        )
    )
    manifest_failures, frame_by_index = validate_frame_manifest(frame_manifest, protocol)
    failures.extend(manifest_failures)
    row_failures, normalized_rows = validate_review_rows(
        headers=headers,
        rows=review_rows,
        frame_by_index=frame_by_index,
        protocol=protocol,
    )
    failures.extend(row_failures)

    if failures:
        return _fail_closed_report(
            protocol=protocol,
            frame_manifest_file_sha256=frame_manifest_file_sha256,
            attestation=attestation,
            completed_review_form_sha256=completed_review_form_sha256,
            failures=failures,
            package_binding_established=True,
        )

    events = derive_onsets(normalized_rows, protocol)
    matches, unmatched = deterministic_pairing(events, protocol)
    expected = protocol["expected_blinded_package"]
    return {
        "schema": REPORT_SCHEMA,
        "status": "PASS",
        "scientific_outcome": (
            "VALID_REVIEW_WITH_MATCHES" if matches else "VALID_REVIEW_ZERO_MATCHES"
        ),
        "failures": [],
        "source_id": protocol.get("source_id"),
        "completed_review_form_sha256": completed_review_form_sha256,
        "frame_manifest_file_sha256": frame_manifest_file_sha256,
        "reviewer_attestation_sha256": canonical_sha256(attestation),
        "blinded_package_content_identity_file_sha256": expected[
            "content_identity_file_sha256"
        ],
        "blinded_package_manifest_sha256": expected["package_manifest_file_sha256"],
        "blinded_package_files_payload_sha256": expected["files_payload_sha256"],
        "blinded_package_transport_sha256": attestation.get(
            "blinded_package_transport_sha256"
        )
        or None,
        "normalized_review_rows": normalized_rows,
        "normalized_review_rows_sha256": canonical_sha256(normalized_rows),
        "derived_onsets": events,
        "derived_onsets_sha256": canonical_sha256(events),
        "matches": matches,
        "matches_sha256": canonical_sha256(matches),
        "unmatched_signaller_event_ids": unmatched,
        "summary": summarize_matches(matches),
        "review_submission_integrity_established": True,
        "exact_frozen_package_binding_established": True,
        "transport_independent_package_content_binding_established": True,
        "independently_reviewed_action_onset_table_established_in_review_scope": True,
        "independent_frame_level_estimate_established": False,
        "claim_ceiling": "A valid independent blinded review submission and deterministic onset/matching replay are established only in review scope and only for the exact canonical blinded package content. Full PILOT_001 biological admission remains separate; no population-level feline latency or causal mimicry claim is established.",
    }
