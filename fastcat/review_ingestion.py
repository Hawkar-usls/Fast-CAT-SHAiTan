from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

REVIEW_HEADERS = [
    "source_id",
    "frame_index",
    "pts_s",
    "subject_id",
    "identity_confirmed",
    "left_ear_EAD103",
    "right_ear_EAD103",
    "left_ear_EAD104",
    "right_ear_EAD104",
    "review_notes",
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


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_review_csv(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return headers, rows


def validate_frame_manifest(
    manifest: dict[str, Any], protocol: dict[str, Any]
) -> tuple[list[str], dict[int, dict[str, Any]]]:
    failures: list[str] = []
    expected = protocol["expected_blinded_package"]
    if manifest.get("schema") != "Fast-CAT/PILOT-001/blinded-review-frame-manifest/v1.0":
        failures.append("FRAME_MANIFEST_SCHEMA_MISMATCH")
    if manifest.get("source_id") != protocol.get("source_id"):
        failures.append("FRAME_MANIFEST_SOURCE_ID_MISMATCH")
    if manifest.get("raw_media_sha256") != expected.get("raw_media_sha256"):
        failures.append("FRAME_MANIFEST_RAW_SHA256_MISMATCH")
    if manifest.get("frame_pts_sha256") != expected.get("frame_pts_sha256"):
        failures.append("FRAME_MANIFEST_PTS_SHA256_MISMATCH")
    if int(manifest.get("frame_count", -1)) != int(expected.get("decoded_frame_count", -2)):
        failures.append("FRAME_MANIFEST_FRAME_COUNT_MISMATCH")
    if manifest.get("contains_model_derived_fields") is not False:
        failures.append("FRAME_MANIFEST_MODEL_DERIVED_FIELDS_NOT_FALSE")

    frames = manifest.get("frames")
    if not isinstance(frames, list):
        return failures + ["FRAME_MANIFEST_FRAMES_INVALID"], {}
    by_index: dict[int, dict[str, Any]] = {}
    last_pts: float | None = None
    for position, frame in enumerate(frames):
        if not isinstance(frame, dict):
            failures.append(f"FRAME_{position}:NOT_OBJECT")
            continue
        try:
            index = int(frame["frame_index"])
            pts = float(frame["pts_s"])
            if not math.isfinite(pts) or pts < 0:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            failures.append(f"FRAME_{position}:INDEX_OR_PTS_INVALID")
            continue
        if index != position:
            failures.append(f"FRAME_{position}:INDEX_SEQUENCE_MISMATCH")
        if index in by_index:
            failures.append(f"FRAME_{position}:DUPLICATE_INDEX")
        if last_pts is not None and pts <= last_pts:
            failures.append(f"FRAME_{position}:PTS_NOT_STRICT")
        last_pts = pts
        by_index[index] = frame
    return failures, by_index


def validate_attestation(
    attestation: dict[str, Any],
    *,
    completed_review_form_sha256: str,
) -> list[str]:
    failures: list[str] = []
    if attestation.get("schema") != "Fast-CAT/PILOT-001/reviewer-attestation/v1.0":
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
    return failures


def validate_review_rows(
    *,
    headers: list[str],
    rows: list[dict[str, str]],
    frame_by_index: dict[int, dict[str, Any]],
    protocol: dict[str, Any],
) -> tuple[list[str], list[dict[str, Any]]]:
    failures: list[str] = []
    expected = protocol["expected_blinded_package"]
    if headers != REVIEW_HEADERS:
        failures.append("REVIEW_HEADERS_MISMATCH_OR_MODEL_FIELDS_PRESENT")

    expected_rows = int(expected["expected_annotation_rows"])
    if len(rows) != expected_rows:
        failures.append(f"REVIEW_ROW_COUNT_MISMATCH:{len(rows)}!={expected_rows}")

    subjects = list(expected["subjects"])
    allowed_states = set(protocol["allowed_review_states"])
    allowed_identity = set(protocol["allowed_identity_states"])
    expected_pairs = [
        (frame_index, subject)
        for frame_index in range(int(expected["decoded_frame_count"]))
        for subject in subjects
    ]

    normalized: list[dict[str, Any]] = []
    actual_pairs: list[tuple[int, str]] = []
    for row_number, row in enumerate(rows):
        prefix = f"ROW_{row_number}"
        try:
            frame_index = int(row.get("frame_index", ""))
        except (TypeError, ValueError):
            failures.append(f"{prefix}:FRAME_INDEX_INVALID")
            continue
        subject_id = str(row.get("subject_id", ""))
        actual_pairs.append((frame_index, subject_id))
        frame = frame_by_index.get(frame_index)
        if frame is None:
            failures.append(f"{prefix}:FRAME_NOT_IN_MANIFEST")
            continue
        if row.get("source_id") != protocol.get("source_id"):
            failures.append(f"{prefix}:SOURCE_ID_MISMATCH")
        if subject_id not in subjects:
            failures.append(f"{prefix}:SUBJECT_ID_INVALID")
        if str(row.get("pts_s")) != str(frame.get("pts_s")):
            failures.append(f"{prefix}:PTS_MISMATCH")

        identity = str(row.get("identity_confirmed", ""))
        if identity not in allowed_identity:
            failures.append(f"{prefix}:IDENTITY_STATE_INVALID")

        states: dict[str, str] = {}
        for channel in CHANNELS:
            state = str(row.get(channel, ""))
            states[channel] = state
            if state not in allowed_states:
                failures.append(f"{prefix}:{channel}:STATE_INVALID")

        normalized.append(
            {
                "source_id": str(row.get("source_id", "")),
                "frame_index": frame_index,
                "pts_s": str(frame.get("pts_s")),
                "subject_id": subject_id,
                "identity_confirmed": identity,
                **states,
                "review_notes": str(row.get("review_notes", "")),
            }
        )

    if actual_pairs != expected_pairs:
        failures.append("REVIEW_ROW_ORDER_OR_COVERAGE_MISMATCH")
    return failures, normalized


def derive_onsets(
    rows: Iterable[dict[str, Any]], protocol: dict[str, Any]
) -> list[dict[str, Any]]:
    rows = list(rows)
    expected = protocol["expected_blinded_package"]
    subjects = list(expected["subjects"])
    by_subject: dict[str, list[dict[str, Any]]] = {subject: [] for subject in subjects}
    for row in rows:
        subject = str(row["subject_id"])
        if subject in by_subject:
            by_subject[subject].append(row)
    for subject in subjects:
        by_subject[subject].sort(key=lambda x: int(x["frame_index"]))

    events: list[dict[str, Any]] = []
    for subject in subjects:
        seq = by_subject[subject]
        for previous, current in zip(seq, seq[1:]):
            if int(current["frame_index"]) != int(previous["frame_index"]) + 1:
                raise ValueError(f"NON_ADJACENT_REVIEW_ROWS:{subject}")
            if previous["identity_confirmed"] != "yes" or current["identity_confirmed"] != "yes":
                continue
            for channel, (action, laterality) in CHANNELS.items():
                if previous[channel] == "ABSENT" and current[channel] == "PRESENT":
                    frame_index = int(current["frame_index"])
                    event_id = f"{subject}:{action}:{laterality}:f{frame_index:06d}"
                    events.append(
                        {
                            "event_id": event_id,
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
    events.sort(
        key=lambda x: (
            float(x["onset_pts_s"]),
            str(x["subject_id"]),
            str(x["action"]),
            str(x["laterality"]),
            str(x["event_id"]),
        )
    )
    return events


def acquisition_interval_ms(
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


def deterministic_pairing(
    events: Iterable[dict[str, Any]], protocol: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    events = sorted(
        list(events),
        key=lambda x: (
            float(x["onset_pts_s"]),
            str(x["event_id"]),
        ),
    )
    window_ms = float(protocol["matching"]["point_estimate_window_ms"])
    used_responses: set[str] = set()
    matched_signallers: set[str] = set()
    matches: list[dict[str, Any]] = []

    for signaller in events:
        s_time = float(signaller["onset_pts_s"])
        candidate: dict[str, Any] | None = None
        for responder in events:
            if responder["event_id"] == signaller["event_id"]:
                continue
            if responder["event_id"] in used_responses:
                continue
            if responder["subject_id"] == signaller["subject_id"]:
                continue
            if responder["action"] != signaller["action"]:
                continue
            r_time = float(responder["onset_pts_s"])
            dt_ms = (r_time - s_time) * 1000.0
            if dt_ms < 0:
                continue
            if dt_ms > window_ms:
                continue
            candidate = responder
            break
        if candidate is None:
            continue

        interval = acquisition_interval_ms(signaller, candidate)
        used_responses.add(str(candidate["event_id"]))
        matched_signallers.add(str(signaller["event_id"]))
        matches.append(
            {
                "match_id": f"{signaller['event_id']}->{candidate['event_id']}",
                "source_id": signaller["source_id"],
                "action": signaller["action"],
                "signaller_event_id": signaller["event_id"],
                "responder_event_id": candidate["event_id"],
                "signaller_subject_id": signaller["subject_id"],
                "responder_subject_id": candidate["subject_id"],
                "signaller_laterality": signaller["laterality"],
                "responder_laterality": candidate["laterality"],
                "signaller_onset_pts_s": float(signaller["onset_pts_s"]),
                "responder_onset_pts_s": float(candidate["onset_pts_s"]),
                "latency_ms": interval["point_ms"],
                "acquisition_interval_ms": interval,
                "interval_boundary_ambiguous": bool(
                    interval["lower_ms"] < 0.0
                    or interval["upper_ms"] > window_ms
                ),
            }
        )

    unmatched = [
        str(event["event_id"])
        for event in events
        if str(event["event_id"]) not in matched_signallers
    ]
    return matches, unmatched


def summarize_matches(matches: Iterable[dict[str, Any]]) -> dict[str, Any]:
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
        if n % 2 == 1
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


def build_submission_report(
    *,
    protocol: dict[str, Any],
    frame_manifest: dict[str, Any],
    headers: list[str],
    review_rows: list[dict[str, str]],
    attestation: dict[str, Any],
    completed_review_form_sha256: str,
) -> dict[str, Any]:
    failures: list[str] = []
    manifest_failures, frame_by_index = validate_frame_manifest(frame_manifest, protocol)
    failures.extend(manifest_failures)
    failures.extend(
        validate_attestation(
            attestation,
            completed_review_form_sha256=completed_review_form_sha256,
        )
    )
    row_failures, normalized_rows = validate_review_rows(
        headers=headers,
        rows=review_rows,
        frame_by_index=frame_by_index,
        protocol=protocol,
    )
    failures.extend(row_failures)

    events: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    unmatched: list[str] = []
    if not failures:
        events = derive_onsets(normalized_rows, protocol)
        matches, unmatched = deterministic_pairing(events, protocol)

    valid = not failures
    summary = summarize_matches(matches)
    outcome = (
        "VALID_REVIEW_WITH_MATCHES"
        if valid and matches
        else "VALID_REVIEW_ZERO_MATCHES"
        if valid
        else "INVALID_SUBMISSION"
    )
    return {
        "schema": "Fast-CAT/PILOT-001/independent-review-ingestion/v1.0",
        "status": "PASS" if valid else "FAIL",
        "scientific_outcome": outcome,
        "failures": failures,
        "source_id": protocol.get("source_id"),
        "completed_review_form_sha256": completed_review_form_sha256,
        "reviewer_attestation_sha256": canonical_sha256(attestation),
        "normalized_review_rows": normalized_rows if valid else [],
        "normalized_review_rows_sha256": canonical_sha256(normalized_rows) if valid else None,
        "derived_onsets": events,
        "derived_onsets_sha256": canonical_sha256(events),
        "matches": matches,
        "matches_sha256": canonical_sha256(matches),
        "unmatched_signaller_event_ids": unmatched,
        "summary": summary,
        "review_submission_integrity_established": valid,
        "independently_reviewed_action_onset_table_established_in_review_scope": valid,
        "independent_frame_level_estimate_established": False,
        "claim_ceiling": (
            "A valid independent blinded review submission and its deterministic onset/matching replay are established in review scope only. Full PILOT_001 admission remains separate; no population-level feline latency or causal mimicry claim is established."
            if valid
            else "Submission failed closed; no independent review or latency claim is admitted."
        ),
    }
