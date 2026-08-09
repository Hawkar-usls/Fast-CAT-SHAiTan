from __future__ import annotations

from typing import Any

from fastcat.review_ingestion import (
    build_submission_report,
    canonical_sha256,
    summarize_matches,
)
from fastcat.review_submission_binding import validate_frozen_package_binding


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
    """Production PILOT_001 review-ingestion boundary.

    The lower-level review parser can validate labels and derive events, but the
    production admission path must first prove that those labels refer to the
    exact frozen model-blinded package. If package lineage fails, no onset or
    match derivation is attempted and the report is returned in a fail-closed
    state.
    """

    binding_failures = validate_frozen_package_binding(
        protocol=protocol,
        frame_manifest_file_sha256=frame_manifest_file_sha256,
        attestation=attestation,
    )
    if binding_failures:
        empty: list[dict[str, Any]] = []
        return {
            "schema": "Fast-CAT/PILOT-001/independent-review-ingestion/v1.1",
            "status": "FAIL",
            "scientific_outcome": "INVALID_SUBMISSION",
            "failures": binding_failures,
            "source_id": protocol.get("source_id"),
            "completed_review_form_sha256": completed_review_form_sha256,
            "frame_manifest_file_sha256": frame_manifest_file_sha256,
            "reviewer_attestation_sha256": canonical_sha256(attestation),
            "normalized_review_rows": [],
            "normalized_review_rows_sha256": None,
            "derived_onsets": [],
            "derived_onsets_sha256": canonical_sha256(empty),
            "matches": [],
            "matches_sha256": canonical_sha256(empty),
            "unmatched_signaller_event_ids": [],
            "summary": summarize_matches([]),
            "review_submission_integrity_established": False,
            "exact_frozen_package_binding_established": False,
            "independently_reviewed_action_onset_table_established_in_review_scope": False,
            "independent_frame_level_estimate_established": False,
            "claim_ceiling": "Exact frozen blinded-package lineage failed closed; labels are not parsed into biological events and no independent review or latency claim is admitted.",
        }

    report = build_submission_report(
        protocol=protocol,
        frame_manifest=frame_manifest,
        headers=headers,
        review_rows=review_rows,
        attestation=attestation,
        completed_review_form_sha256=completed_review_form_sha256,
    )
    report["schema"] = "Fast-CAT/PILOT-001/independent-review-ingestion/v1.1"
    report["frame_manifest_file_sha256"] = frame_manifest_file_sha256
    report["exact_frozen_package_binding_established"] = report["status"] == "PASS"
    return report
