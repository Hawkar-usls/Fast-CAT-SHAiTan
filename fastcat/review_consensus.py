from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

STATE_FIELDS = [
    "identity_confirmed",
    "left_ear_EAD103",
    "right_ear_EAD103",
    "left_ear_EAD104",
    "right_ear_EAD104",
]

CHANNELS = {
    "left_ear_EAD103": ("EAD103", "left"),
    "right_ear_EAD103": ("EAD103", "right"),
    "left_ear_EAD104": ("EAD104", "left"),
    "right_ear_EAD104": ("EAD104", "right"),
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _row_key(row: dict[str, Any]) -> tuple[str, int, str, str]:
    return (
        str(row.get("source_id", "")),
        int(row.get("frame_index", -1)),
        str(row.get("pts_s", "")),
        str(row.get("subject_id", "")),
    )


def _derive_review_onsets(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    subjects = sorted({str(row["subject_id"]) for row in rows})
    by_subject: dict[str, list[dict[str, Any]]] = {subject: [] for subject in subjects}
    for row in rows:
        by_subject[str(row["subject_id"])].append(row)
    events: list[dict[str, Any]] = []
    for subject in subjects:
        seq = sorted(by_subject[subject], key=lambda x: int(x["frame_index"]))
        for previous, current in zip(seq, seq[1:]):
            if int(current["frame_index"]) != int(previous["frame_index"]) + 1:
                raise ValueError(f"NON_ADJACENT_REVIEW_ROWS:{subject}")
            if previous["identity_confirmed"] != "yes" or current["identity_confirmed"] != "yes":
                continue
            for channel, (action, laterality) in CHANNELS.items():
                if previous[channel] == "ABSENT" and current[channel] == "PRESENT":
                    frame_index = int(current["frame_index"])
                    events.append(
                        {
                            "event_id": f"{subject}:{action}:{laterality}:f{frame_index:06d}",
                            "source_id": str(current["source_id"]),
                            "subject_id": subject,
                            "action": action,
                            "laterality": laterality,
                            "previous_absent_frame_index": int(previous["frame_index"]),
                            "previous_absent_pts_s": float(previous["pts_s"]),
                            "onset_frame_index": frame_index,
                            "onset_pts_s": float(current["pts_s"]),
                            "event_source": "manual_catfacs_frame_review",
                            "review_state_transition": "ABSENT->PRESENT",
                        }
                    )
    return sorted(
        events,
        key=lambda x: (
            float(x["onset_pts_s"]),
            str(x["subject_id"]),
            str(x["action"]),
            str(x["laterality"]),
            str(x["event_id"]),
        ),
    )


def _validate_submission_bundle(
    bundle: dict[str, Any], index: int, window_ms: float
) -> list[str]:
    prefix = f"REVIEW_{index}"
    failures: list[str] = []
    analysis = bundle.get("analysis")
    attestation = bundle.get("attestation")
    verifier = bundle.get("verifier")
    if not isinstance(analysis, dict):
        return [f"{prefix}:ANALYSIS_REPORT_MISSING"]
    if not isinstance(attestation, dict):
        return [f"{prefix}:ATTESTATION_MISSING"]
    if not isinstance(verifier, dict):
        return [f"{prefix}:VERIFIER_REPORT_MISSING"]

    if analysis.get("status") != "PASS":
        failures.append(f"{prefix}:ANALYSIS_NOT_PASS")
    if analysis.get("exact_frozen_package_binding_established") is not True:
        failures.append(f"{prefix}:EXACT_PACKAGE_BINDING_NOT_ESTABLISHED")
    if analysis.get("review_submission_integrity_established") is not True:
        failures.append(f"{prefix}:SUBMISSION_INTEGRITY_NOT_ESTABLISHED")
    if analysis.get("independent_frame_level_estimate_established") is not False:
        failures.append(f"{prefix}:ANALYSIS_SELF_PROMOTED_FINAL_ESTIMATE")

    if verifier.get("status") != "PASS":
        failures.append(f"{prefix}:VERIFIER_NOT_PASS")
    if verifier.get("independent_replay_established") is not True:
        failures.append(f"{prefix}:INDEPENDENT_REPLAY_NOT_ESTABLISHED")
    if verifier.get("independent_frame_level_estimate_established") is not False:
        failures.append(f"{prefix}:VERIFIER_SELF_PROMOTED_FINAL_ESTIMATE")

    reviewer_id = str(attestation.get("reviewer_id", "")).strip()
    if not reviewer_id:
        failures.append(f"{prefix}:REVIEWER_ID_MISSING")
    if canonical_sha256(attestation) != analysis.get("reviewer_attestation_sha256"):
        failures.append(f"{prefix}:ATTESTATION_CANONICAL_SHA256_MISMATCH")

    rows = analysis.get("normalized_review_rows")
    if not isinstance(rows, list) or not rows:
        failures.append(f"{prefix}:NORMALIZED_ROWS_MISSING")
    elif analysis.get("normalized_review_rows_sha256") != canonical_sha256(rows):
        failures.append(f"{prefix}:NORMALIZED_ROWS_SHA256_MISMATCH")
    else:
        try:
            replayed_onsets = _derive_review_onsets(rows)
            replayed_matches, _ = _deterministic_pairing(replayed_onsets, window_ms)
            if analysis.get("derived_onsets_sha256") != canonical_sha256(replayed_onsets):
                failures.append(f"{prefix}:ANALYSIS_DERIVED_ONSETS_REPLAY_MISMATCH")
            if analysis.get("matches_sha256") != canonical_sha256(replayed_matches):
                failures.append(f"{prefix}:ANALYSIS_MATCHES_REPLAY_MISMATCH")
        except (KeyError, TypeError, ValueError) as exc:
            failures.append(f"{prefix}:INTERNAL_REPLAY_FAILED:{type(exc).__name__}")

    if verifier.get("frame_manifest_file_sha256") != analysis.get("frame_manifest_file_sha256"):
        failures.append(f"{prefix}:VERIFIER_FRAME_MANIFEST_BINDING_MISMATCH")
    if verifier.get("normalized_review_rows_sha256_recomputed") != analysis.get("normalized_review_rows_sha256"):
        failures.append(f"{prefix}:VERIFIER_NORMALIZED_ROWS_SHA256_MISMATCH")
    if verifier.get("derived_onsets_sha256_recomputed") != analysis.get("derived_onsets_sha256"):
        failures.append(f"{prefix}:VERIFIER_DERIVED_ONSETS_SHA256_MISMATCH")
    if verifier.get("matches_sha256_recomputed") != analysis.get("matches_sha256"):
        failures.append(f"{prefix}:VERIFIER_MATCHES_SHA256_MISMATCH")
    return failures


def _derive_consensus_onsets(
    rows: Iterable[dict[str, Any]], subjects: list[str]
) -> list[dict[str, Any]]:
    by_subject: dict[str, list[dict[str, Any]]] = {subject: [] for subject in subjects}
    for row in rows:
        subject = str(row["subject_id"])
        if subject in by_subject:
            by_subject[subject].append(row)
    events: list[dict[str, Any]] = []
    for subject in subjects:
        seq = sorted(by_subject[subject], key=lambda x: int(x["frame_index"]))
        for previous, current in zip(seq, seq[1:]):
            if int(current["frame_index"]) != int(previous["frame_index"]) + 1:
                raise ValueError(f"NON_ADJACENT_CONSENSUS_ROWS:{subject}")
            if previous["identity_confirmed"] != "yes" or current["identity_confirmed"] != "yes":
                continue
            for channel, (action, laterality) in CHANNELS.items():
                if previous[channel] == "ABSENT" and current[channel] == "PRESENT":
                    frame_index = int(current["frame_index"])
                    events.append(
                        {
                            "event_id": f"{subject}:{action}:{laterality}:f{frame_index:06d}",
                            "source_id": str(current["source_id"]),
                            "subject_id": subject,
                            "action": action,
                            "laterality": laterality,
                            "previous_absent_frame_index": int(previous["frame_index"]),
                            "previous_absent_pts_s": float(previous["pts_s"]),
                            "onset_frame_index": frame_index,
                            "onset_pts_s": float(current["pts_s"]),
                            "event_source": "multi_reviewer_unanimous_manual_catfacs_consensus",
                            "review_state_transition": "UNANIMOUS_ABSENT->UNANIMOUS_PRESENT",
                        }
                    )
    return sorted(
        events,
        key=lambda x: (
            float(x["onset_pts_s"]),
            str(x["subject_id"]),
            str(x["action"]),
            str(x["laterality"]),
            str(x["event_id"]),
        ),
    )


def _acquisition_interval_ms(
    signaller: dict[str, Any], responder: dict[str, Any]
) -> dict[str, float]:
    s_prev = float(signaller["previous_absent_pts_s"])
    s = float(signaller["onset_pts_s"])
    r_prev = float(responder["previous_absent_pts_s"])
    r = float(responder["onset_pts_s"])
    if not (0 <= s_prev < s <= r and 0 <= r_prev < r):
        raise ValueError("EVENT_PTS_BRACKET_INVALID")
    point = (r - s) * 1000.0
    lower = (r_prev - s) * 1000.0
    upper = (r - s_prev) * 1000.0
    return {
        "point_ms": point,
        "lower_ms": lower,
        "upper_ms": upper,
        "signaller_bracket_ms": (s - s_prev) * 1000.0,
        "responder_bracket_ms": (r - r_prev) * 1000.0,
        "interval_width_ms": upper - lower,
    }


def _deterministic_pairing(
    events: Iterable[dict[str, Any]], window_ms: float
) -> tuple[list[dict[str, Any]], list[str]]:
    ordered = sorted(
        list(events), key=lambda x: (float(x["onset_pts_s"]), str(x["event_id"]))
    )
    used_responses: set[str] = set()
    matched_signallers: set[str] = set()
    matches: list[dict[str, Any]] = []
    for signaller in ordered:
        chosen: dict[str, Any] | None = None
        for responder in ordered:
            if responder["event_id"] == signaller["event_id"]:
                continue
            if responder["event_id"] in used_responses:
                continue
            if responder["subject_id"] == signaller["subject_id"]:
                continue
            if responder["action"] != signaller["action"]:
                continue
            dt_ms = (
                float(responder["onset_pts_s"]) - float(signaller["onset_pts_s"])
            ) * 1000.0
            if 0.0 <= dt_ms <= window_ms:
                chosen = responder
                break
        if chosen is None:
            continue
        interval = _acquisition_interval_ms(signaller, chosen)
        used_responses.add(str(chosen["event_id"]))
        matched_signallers.add(str(signaller["event_id"]))
        matches.append(
            {
                "match_id": f"{signaller['event_id']}->{chosen['event_id']}",
                "source_id": signaller["source_id"],
                "action": signaller["action"],
                "signaller_event_id": signaller["event_id"],
                "responder_event_id": chosen["event_id"],
                "signaller_subject_id": signaller["subject_id"],
                "responder_subject_id": chosen["subject_id"],
                "signaller_laterality": signaller["laterality"],
                "responder_laterality": chosen["laterality"],
                "signaller_onset_pts_s": float(signaller["onset_pts_s"]),
                "responder_onset_pts_s": float(chosen["onset_pts_s"]),
                "latency_ms": interval["point_ms"],
                "acquisition_interval_ms": interval,
                "interval_boundary_ambiguous": bool(
                    interval["lower_ms"] < 0.0 or interval["upper_ms"] > window_ms
                ),
            }
        )
    unmatched = [
        str(event["event_id"])
        for event in ordered
        if str(event["event_id"]) not in matched_signallers
    ]
    return matches, unmatched


def _summarize_matches(matches: Iterable[dict[str, Any]]) -> dict[str, Any]:
    values = [float(x["latency_ms"]) for x in matches]
    if not values:
        return {
            "n_matches": 0,
            "latencies_ms": [],
            "mean_ms": None,
            "median_ms": None,
            "min_ms": None,
            "max_ms": None,
        }
    ordered = sorted(values)
    n = len(ordered)
    median = (
        ordered[n // 2]
        if n % 2
        else (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0
    )
    return {
        "n_matches": len(values),
        "latencies_ms": values,
        "mean_ms": sum(values) / len(values),
        "median_ms": median,
        "min_ms": min(values),
        "max_ms": max(values),
    }


def build_consensus_report(
    *, bundles: list[dict[str, Any]], policy: dict[str, Any]
) -> dict[str, Any]:
    failures: list[str] = []
    required = int(policy.get("required_reviewers", 2))
    if len(bundles) < required:
        failures.append(f"REVIEWER_COUNT_BELOW_REQUIRED:{len(bundles)}<{required}")

    window_ms = float(policy.get("point_estimate_window_ms", 1000.0))
    for index, bundle in enumerate(bundles):
        failures.extend(_validate_submission_bundle(bundle, index, window_ms))

    analyses = [bundle.get("analysis", {}) for bundle in bundles]
    attestations = [bundle.get("attestation", {}) for bundle in bundles]
    reviewer_ids = [
        str(attestation.get("reviewer_id", "")).strip()
        for attestation in attestations
    ]
    attestation_hashes = [canonical_sha256(attestation) for attestation in attestations]

    if policy.get("distinct_reviewer_ids_required", True) and len(
        set(reviewer_ids)
    ) != len(reviewer_ids):
        failures.append("REVIEWER_IDS_NOT_DISTINCT")
    if policy.get("distinct_attestation_hashes_required", True) and len(
        set(attestation_hashes)
    ) != len(attestation_hashes):
        failures.append("ATTESTATION_HASHES_NOT_DISTINCT")

    sources = {str(analysis.get("source_id", "")) for analysis in analyses}
    manifests = {
        str(analysis.get("frame_manifest_file_sha256", "")) for analysis in analyses
    }
    if len(sources) > 1:
        failures.append("SOURCE_ID_MISMATCH_ACROSS_REVIEWS")
    if len(manifests) > 1:
        failures.append("FRAME_MANIFEST_BINDING_MISMATCH_ACROSS_REVIEWS")

    rows_by_review = [analysis.get("normalized_review_rows", []) for analysis in analyses]
    if analyses and all(isinstance(rows, list) for rows in rows_by_review):
        reference_keys = (
            [_row_key(row) for row in rows_by_review[0]] if rows_by_review else []
        )
        for index, rows in enumerate(rows_by_review[1:], start=1):
            if [_row_key(row) for row in rows] != reference_keys:
                failures.append(f"REVIEW_{index}:ROW_KEY_ALIGNMENT_MISMATCH")

    if failures:
        empty: list[dict[str, Any]] = []
        return {
            "schema": "Fast-CAT/PILOT-001/multi-reviewer-consensus/v1.0",
            "status": "FAIL",
            "failures": failures,
            "reviewer_count": len(bundles),
            "reviewer_ids": reviewer_ids,
            "consensus_rows": [],
            "consensus_rows_sha256": canonical_sha256(empty),
            "derived_consensus_onsets": [],
            "derived_consensus_onsets_sha256": canonical_sha256(empty),
            "matches": [],
            "matches_sha256": canonical_sha256(empty),
            "agreement": None,
            "multi_reviewer_consensus_established_in_review_scope": False,
            "independent_frame_level_estimate_established": False,
            "claim_ceiling": "Multi-reviewer gate failed closed; no consensus action onset or latency result is admitted.",
        }

    reference = rows_by_review[0]
    consensus_rows: list[dict[str, Any]] = []
    unanimous_cells = 0
    total_cells = len(reference) * len(STATE_FIELDS)
    field_stats = {
        field: {"unanimous": 0, "disagreement": 0} for field in STATE_FIELDS
    }

    for row_index, base in enumerate(reference):
        consensus = {
            "source_id": str(base["source_id"]),
            "frame_index": int(base["frame_index"]),
            "pts_s": str(base["pts_s"]),
            "subject_id": str(base["subject_id"]),
        }
        for field in STATE_FIELDS:
            values = [str(rows[row_index][field]) for rows in rows_by_review]
            if len(set(values)) == 1:
                value = values[0]
                unanimous_cells += 1
                field_stats[field]["unanimous"] += 1
            else:
                value = "DISAGREEMENT"
                field_stats[field]["disagreement"] += 1
            consensus[field] = value
        consensus_rows.append(consensus)

    agreement = {
        "state_cell_count": total_cells,
        "unanimous_state_cell_count": unanimous_cells,
        "disagreement_state_cell_count": total_cells - unanimous_cells,
        "exact_state_agreement_rate": (
            unanimous_cells / total_cells if total_cells else None
        ),
        "by_field": field_stats,
    }

    subjects = sorted({str(row["subject_id"]) for row in consensus_rows})
    events = _derive_consensus_onsets(consensus_rows, subjects)
    matches, unmatched = _deterministic_pairing(events, window_ms)
    summary = _summarize_matches(matches)

    scientific_outcome = (
        "VALID_UNANIMOUS_CONSENSUS_WITH_MATCHES"
        if matches
        else "VALID_UNANIMOUS_CONSENSUS_ZERO_MATCHES"
    )
    return {
        "schema": "Fast-CAT/PILOT-001/multi-reviewer-consensus/v1.0",
        "status": "PASS",
        "scientific_outcome": scientific_outcome,
        "failures": [],
        "source_id": next(iter(sources)) if sources else None,
        "frame_manifest_file_sha256": next(iter(manifests)) if manifests else None,
        "reviewer_count": len(bundles),
        "reviewer_ids": reviewer_ids,
        "reviewer_attestation_sha256s": attestation_hashes,
        "input_analysis_report_sha256s": [
            canonical_sha256(analysis) for analysis in analyses
        ],
        "input_verifier_report_sha256s": [
            canonical_sha256(bundle["verifier"]) for bundle in bundles
        ],
        "consensus_rows": consensus_rows,
        "consensus_rows_sha256": canonical_sha256(consensus_rows),
        "agreement": agreement,
        "derived_consensus_onsets": events,
        "derived_consensus_onsets_sha256": canonical_sha256(events),
        "matches": matches,
        "matches_sha256": canonical_sha256(matches),
        "unmatched_signaller_event_ids": unmatched,
        "summary": summary,
        "multi_reviewer_consensus_established_in_review_scope": True,
        "independent_frame_level_estimate_established": False,
        "claim_ceiling": "Distinct valid independently verified blinded reviews may establish a unanimous frame-state consensus and deterministic onset/matching replay in review scope only. Disagreement is preserved and never imputed. Landmark accuracy, independent subject identity outside reviewer scope, population-level feline latency, causal mimicry and INDEPENDENT_FRAME_LEVEL_ESTIMATE remain not established.",
    }
