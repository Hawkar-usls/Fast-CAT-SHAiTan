from __future__ import annotations

from typing import Any


def classify_full_rate_control(
    *,
    expected_frames: int,
    processed_frames: int,
    distinct_two_candidate_frames: int,
    duplicate_face_risk_frames: int,
    incomplete_roi_frames: int,
    integrity_failures: list[str] | None = None,
) -> dict[str, Any]:
    """Classify the full-rate conflict-control candidate-geometry gate.

    A detector coverage miss is a valid scientific negative for this candidate
    backend, not an infrastructure failure. Downstream adjacent-frame ear-motion
    triage is admitted only when every decoded frame has two spatially distinct
    structurally valid candidate faces.
    """

    failures = list(integrity_failures or [])
    counts = {
        "expected_frames": int(expected_frames),
        "processed_frames": int(processed_frames),
        "distinct_two_candidate_frames": int(distinct_two_candidate_frames),
        "duplicate_face_risk_frames": int(duplicate_face_risk_frames),
        "incomplete_roi_frames": int(incomplete_roi_frames),
    }

    if counts["expected_frames"] <= 1:
        failures.append("EXPECTED_FRAME_COUNT_INVALID")
    for name, value in counts.items():
        if value < 0:
            failures.append(f"NEGATIVE_COUNT:{name}")

    if counts["processed_frames"] != counts["expected_frames"]:
        failures.append(
            "PROCESSED_FRAME_COUNT_MISMATCH:"
            f"{counts['processed_frames']}!={counts['expected_frames']}"
        )

    classified = (
        counts["distinct_two_candidate_frames"]
        + counts["duplicate_face_risk_frames"]
        + counts["incomplete_roi_frames"]
    )
    if classified != counts["processed_frames"]:
        failures.append(
            "FRAME_CLASSIFICATION_PARTITION_MISMATCH:"
            f"{classified}!={counts['processed_frames']}"
        )

    if failures:
        return {
            "status": "FAIL",
            "scientific_outcome": "NOT_CLASSIFIED_DUE_TO_INTEGRITY_FAILURE",
            "failures": failures,
            "coverage_fraction": None,
            "adjacent_full_rate_ear_triage_admitted": False,
            **counts,
        }

    coverage_fraction = (
        counts["distinct_two_candidate_frames"] / counts["expected_frames"]
    )
    complete = (
        counts["distinct_two_candidate_frames"] == counts["expected_frames"]
        and counts["duplicate_face_risk_frames"] == 0
        and counts["incomplete_roi_frames"] == 0
    )

    return {
        "status": "PASS_CANDIDATE_ONLY"
        if complete
        else "VALID_NEGATIVE_INCOMPLETE_CANDIDATE_COVERAGE",
        "scientific_outcome": "FULL_RATE_TWO_CANDIDATE_COVERAGE_COMPLETE"
        if complete
        else "FULL_RATE_TWO_CANDIDATE_COVERAGE_INCOMPLETE",
        "failures": [],
        "coverage_fraction": coverage_fraction,
        "adjacent_full_rate_ear_triage_admitted": complete,
        **counts,
    }
