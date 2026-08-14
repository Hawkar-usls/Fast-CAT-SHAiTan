from __future__ import annotations

from typing import Any

FLOAT_FIELDS = (
    "anchor_rms_iod",
    "interocular_distance_px",
    "left_ear_excess_over_anchor_iod",
    "right_ear_excess_over_anchor_iod",
    "max_ear_excess_over_anchor_iod",
    "left_ear_rms_iod",
    "right_ear_rms_iod",
)


def _transition_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["candidate_cat_id"],
        int(row["from_frame_index"]),
        int(row["to_frame_index"]),
        float(row["from_pts_s"]),
        float(row["to_pts_s"]),
    )


def _ranking_key(row: dict[str, Any]) -> tuple[int, int]:
    return (int(row["from_frame_index"]), int(row["to_frame_index"]))


def compare_triage_reports(
    *, baseline: dict[str, Any], candidate: dict[str, Any], protocol: dict[str, Any]
) -> dict[str, Any]:
    failures: list[str] = []
    req = protocol["frozen_validation_requirements"]

    if baseline.get("source_id") != candidate.get("source_id"):
        failures.append("SOURCE_ID_MISMATCH")
    if candidate.get("transition_count") != req["same_transition_count_required"]:
        failures.append("CANDIDATE_TRANSITION_COUNT_MISMATCH")
    if baseline.get("transition_count") != candidate.get("transition_count"):
        failures.append("TRANSITION_COUNT_NOT_REPRODUCED")

    base_rows = {_transition_key(x): x for x in baseline.get("transitions", [])}
    cand_rows = {_transition_key(x): x for x in candidate.get("transitions", [])}
    if set(base_rows) != set(cand_rows):
        failures.append("TRANSITION_KEY_SET_MISMATCH")

    limits = req["floating_max_absolute_difference_limits"]
    maxima = {field: 0.0 for field in FLOAT_FIELDS}
    compared = 0
    for key in sorted(set(base_rows) & set(cand_rows)):
        compared += 1
        for field in FLOAT_FIELDS:
            delta = abs(float(base_rows[key][field]) - float(cand_rows[key][field]))
            maxima[field] = max(maxima[field], delta)
    for field, observed in maxima.items():
        if observed > float(limits[field]):
            failures.append(
                f"FLOAT_TOLERANCE_EXCEEDED:{field}:{observed}>{limits[field]}"
            )

    k = int(req["top_k_ranking_set"])
    minimum_overlap = int(req["minimum_top_k_set_overlap_per_candidate_cat"])
    overlaps: dict[str, int] = {}
    base_rankings = baseline.get("rankings", {})
    cand_rankings = candidate.get("rankings", {})
    cats = sorted(set(base_rankings) | set(cand_rankings))
    for cat in cats:
        a = {_ranking_key(x) for x in base_rankings.get(cat, [])[:k]}
        b = {_ranking_key(x) for x in cand_rankings.get(cat, [])[:k]}
        overlap = len(a & b)
        overlaps[cat] = overlap
        if overlap < minimum_overlap:
            failures.append(
                f"TOP_K_SET_OVERLAP_BELOW_REQUIRED:{cat}:{overlap}<{minimum_overlap}"
            )

    return {
        "schema": "Fast-CAT/PILOT-001/numerical-reproducibility-comparison/v1.0",
        "status": (
            "VALIDATED_WITHIN_FROZEN_NUMERICAL_TOLERANCE"
            if not failures
            else "NUMERICAL_REPRODUCIBILITY_OUTSIDE_FROZEN_TOLERANCE"
        ),
        "failures": failures,
        "transition_count_baseline": baseline.get("transition_count"),
        "transition_count_candidate": candidate.get("transition_count"),
        "transition_keys_compared": compared,
        "transition_key_set_exact_match": set(base_rows) == set(cand_rows),
        "max_absolute_difference": maxima,
        "top_k_set_overlap_per_candidate_cat": overlaps,
        "byte_identical_float_hashes_required": False,
        "claim_ceiling": protocol["claim_ceiling"],
    }
