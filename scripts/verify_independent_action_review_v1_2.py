#!/usr/bin/env python3
"""Independently replay a PILOT_001 v1.2 blinded-review submission.

This verifier does not import the production ingestion implementation. It
independently checks transport-independent canonical package bindings, reviewer
attestation semantics, CSV/frame lineage, ABSENT->PRESENT onset derivation and
deterministic cross-subject pairing, then compares those recomputations with
the analysis report.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

HEADERS = [
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
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def derive(rows: list[dict[str, Any]], subjects: list[str]) -> list[dict[str, Any]]:
    by = {subject: [] for subject in subjects}
    for row in rows:
        by[row["subject_id"]].append(row)
    out: list[dict[str, Any]] = []
    for subject in subjects:
        seq = sorted(by[subject], key=lambda x: x["frame_index"])
        for previous, current in zip(seq, seq[1:]):
            if current["frame_index"] != previous["frame_index"] + 1:
                raise RuntimeError(f"NON_ADJACENT_ROWS:{subject}")
            if (
                previous["identity_confirmed"] != "yes"
                or current["identity_confirmed"] != "yes"
            ):
                continue
            for channel, (action, laterality) in CHANNELS.items():
                if previous[channel] == "ABSENT" and current[channel] == "PRESENT":
                    frame_index = current["frame_index"]
                    out.append(
                        {
                            "event_id": f"{subject}:{action}:{laterality}:f{frame_index:06d}",
                            "source_id": current["source_id"],
                            "subject_id": subject,
                            "action": action,
                            "laterality": laterality,
                            "previous_absent_frame_index": previous["frame_index"],
                            "previous_absent_pts_s": float(previous["pts_s"]),
                            "onset_frame_index": frame_index,
                            "onset_pts_s": float(current["pts_s"]),
                            "event_source": "manual_catfacs_frame_review",
                            "review_state_transition": "ABSENT->PRESENT",
                        }
                    )
    return sorted(
        out,
        key=lambda x: (
            x["onset_pts_s"],
            x["subject_id"],
            x["action"],
            x["laterality"],
            x["event_id"],
        ),
    )


def interval(signaller: dict[str, Any], responder: dict[str, Any]) -> dict[str, float]:
    s_prev = float(signaller["previous_absent_pts_s"])
    s = float(signaller["onset_pts_s"])
    r_prev = float(responder["previous_absent_pts_s"])
    r = float(responder["onset_pts_s"])
    if not (0 <= s_prev < s <= r and 0 <= r_prev < r):
        raise RuntimeError("EVENT_PTS_BRACKET_INVALID")
    return {
        "point_ms": (r - s) * 1000.0,
        "lower_ms": (r_prev - s) * 1000.0,
        "upper_ms": (r - s_prev) * 1000.0,
        "signaller_bracket_ms": (s - s_prev) * 1000.0,
        "responder_bracket_ms": (r - r_prev) * 1000.0,
        "interval_width_ms": ((r - s_prev) - (r_prev - s)) * 1000.0,
    }


def pair(
    events: list[dict[str, Any]], window_ms: float
) -> tuple[list[dict[str, Any]], list[str]]:
    ordered = sorted(events, key=lambda x: (float(x["onset_pts_s"]), x["event_id"]))
    used: set[str] = set()
    matched: set[str] = set()
    matches: list[dict[str, Any]] = []
    for signaller in ordered:
        chosen = None
        for responder in ordered:
            if (
                responder["event_id"] == signaller["event_id"]
                or responder["event_id"] in used
                or responder["subject_id"] == signaller["subject_id"]
                or responder["action"] != signaller["action"]
            ):
                continue
            dt_ms = (
                float(responder["onset_pts_s"]) - float(signaller["onset_pts_s"])
            ) * 1000.0
            if 0.0 <= dt_ms <= window_ms:
                chosen = responder
                break
        if chosen is None:
            continue
        acquisition = interval(signaller, chosen)
        used.add(chosen["event_id"])
        matched.add(signaller["event_id"])
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
                "latency_ms": acquisition["point_ms"],
                "acquisition_interval_ms": acquisition,
                "interval_boundary_ambiguous": (
                    acquisition["lower_ms"] < 0.0
                    or acquisition["upper_ms"] > window_ms
                ),
            }
        )
    return matches, [
        event["event_id"] for event in ordered if event["event_id"] not in matched
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in (
        "protocol",
        "frame-manifest",
        "review-form",
        "attestation",
        "analysis-report",
        "out",
    ):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    manifest = json.loads(args.frame_manifest.read_text(encoding="utf-8"))
    attestation = json.loads(args.attestation.read_text(encoding="utf-8"))
    analysis = json.loads(args.analysis_report.read_text(encoding="utf-8"))
    failures: list[str] = []
    expected = protocol.get("expected_blinded_package", {})

    if protocol.get("schema") != "Fast-CAT/PILOT-001/independent-review-submission-protocol/v1.2":
        failures.append("SUBMISSION_PROTOCOL_SCHEMA_MISMATCH")
    manifest_sha = sha256_file(args.frame_manifest)
    form_sha = sha256_file(args.review_form)
    if manifest_sha != expected.get("frame_manifest_file_sha256"):
        failures.append("FRAME_MANIFEST_FILE_SHA256_NOT_FROZEN_PACKAGE")
    if manifest.get("source_id") != protocol.get("source_id"):
        failures.append("FRAME_MANIFEST_SOURCE_MISMATCH")
    if manifest.get("raw_media_sha256") != expected.get("raw_media_sha256"):
        failures.append("FRAME_MANIFEST_RAW_SHA256_MISMATCH")
    if manifest.get("frame_pts_sha256") != expected.get("frame_pts_sha256"):
        failures.append("FRAME_MANIFEST_PTS_SHA256_MISMATCH")
    if int(manifest.get("frame_count", -1)) != int(expected.get("decoded_frame_count", -2)):
        failures.append("FRAME_MANIFEST_COUNT_MISMATCH")
    if manifest.get("contains_model_derived_fields") is not False:
        failures.append("FRAME_MANIFEST_MODEL_FIELDS_FLAG_INVALID")

    if attestation.get("schema") != "Fast-CAT/PILOT-001/reviewer-attestation/v1.1":
        failures.append("ATTESTATION_SCHEMA_MISMATCH")
    if not str(attestation.get("reviewer_id", "")).strip():
        failures.append("ATTESTATION_REVIEWER_ID_MISSING")
    if attestation.get("independent_of_fastcat_model_evidence_before_label_freeze") is not True:
        failures.append("ATTESTATION_INDEPENDENCE_NOT_TRUE")
    if attestation.get("saw_landmark_or_motion_rankings_before_label_freeze") is not False:
        failures.append("ATTESTATION_RANKING_EXPOSURE_NOT_FALSE")
    if attestation.get("labels_frozen_before_model_reveal") is not True:
        failures.append("ATTESTATION_LABEL_FREEZE_NOT_TRUE")
    if not str(attestation.get("catfacs_competence_basis", "")).strip():
        failures.append("ATTESTATION_COMPETENCE_BASIS_MISSING")
    if not str(attestation.get("review_completed_utc", "")).strip():
        failures.append("ATTESTATION_COMPLETION_TIME_MISSING")
    if attestation.get("completed_review_form_sha256") != form_sha:
        failures.append("ATTESTATION_FORM_SHA256_MISMATCH")
    bindings = (
        (
            "blinded_package_content_identity_file_sha256",
            "content_identity_file_sha256",
            "ATTESTATION_CONTENT_IDENTITY_FILE_SHA256_MISMATCH",
        ),
        (
            "blinded_package_manifest_sha256",
            "package_manifest_file_sha256",
            "ATTESTATION_PACKAGE_MANIFEST_SHA256_MISMATCH",
        ),
        (
            "blinded_package_files_payload_sha256",
            "files_payload_sha256",
            "ATTESTATION_FILES_PAYLOAD_SHA256_MISMATCH",
        ),
        (
            "blank_review_form_sha256",
            "blank_review_form_sha256",
            "ATTESTATION_BLANK_FORM_SHA256_MISMATCH",
        ),
    )
    for attestation_field, expected_field, code in bindings:
        if str(attestation.get(attestation_field, "")) != str(
            expected.get(expected_field, "")
        ):
            failures.append(code)
    transport = str(attestation.get("blinded_package_transport_sha256", "")).strip()
    if transport and (
        len(transport) != 64
        or any(c not in "0123456789abcdefABCDEF" for c in transport)
    ):
        failures.append("ATTESTATION_TRANSPORT_SHA256_INVALID")

    frames = manifest.get("frames", [])
    by_index: dict[int, dict[str, Any]] = {}
    last = None
    for position, frame in enumerate(frames):
        try:
            frame_index = int(frame["frame_index"])
            pts = float(frame["pts_s"])
            if (
                frame_index != position
                or not math.isfinite(pts)
                or pts < 0
                or (last is not None and pts <= last)
            ):
                raise ValueError
            last = pts
            by_index[frame_index] = frame
        except (KeyError, TypeError, ValueError):
            failures.append(f"FRAME_{position}:INVALID_SEQUENCE_OR_PTS")

    with args.review_form.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        raw_rows = list(reader)
    if headers != HEADERS:
        failures.append("REVIEW_HEADERS_MISMATCH_OR_MODEL_FIELDS_PRESENT")
    if len(raw_rows) != int(expected.get("expected_annotation_rows", -1)):
        failures.append("REVIEW_ROW_COUNT_MISMATCH")
    subjects = list(expected.get("subjects", []))
    allowed_states = set(protocol.get("allowed_review_states", []))
    allowed_identity = set(protocol.get("allowed_identity_states", []))
    expected_pairs = [
        (frame_index, subject)
        for frame_index in range(int(expected.get("decoded_frame_count", 0)))
        for subject in subjects
    ]
    actual_pairs: list[tuple[int, str]] = []
    normalized: list[dict[str, Any]] = []
    for row_index, row in enumerate(raw_rows):
        try:
            frame_index = int(row["frame_index"])
        except (KeyError, TypeError, ValueError):
            failures.append(f"ROW_{row_index}:FRAME_INDEX_INVALID")
            continue
        subject = str(row.get("subject_id", ""))
        actual_pairs.append((frame_index, subject))
        frame = by_index.get(frame_index)
        if frame is None:
            failures.append(f"ROW_{row_index}:FRAME_MISSING")
            continue
        if row.get("source_id") != protocol.get("source_id"):
            failures.append(f"ROW_{row_index}:SOURCE_ID_MISMATCH")
        if subject not in subjects:
            failures.append(f"ROW_{row_index}:SUBJECT_INVALID")
        if str(row.get("pts_s")) != str(frame.get("pts_s")):
            failures.append(f"ROW_{row_index}:PTS_MISMATCH")
        identity = str(row.get("identity_confirmed", ""))
        if identity not in allowed_identity:
            failures.append(f"ROW_{row_index}:IDENTITY_INVALID")
        state_values = {}
        for channel in CHANNELS:
            state = str(row.get(channel, ""))
            state_values[channel] = state
            if state not in allowed_states:
                failures.append(f"ROW_{row_index}:{channel}:STATE_INVALID")
        normalized.append(
            {
                "source_id": str(row.get("source_id", "")),
                "frame_index": frame_index,
                "pts_s": str(frame.get("pts_s")),
                "subject_id": subject,
                "identity_confirmed": identity,
                **state_values,
                "review_notes": str(row.get("review_notes", "")),
            }
        )
    if actual_pairs != expected_pairs:
        failures.append("REVIEW_ORDER_OR_COVERAGE_MISMATCH")

    events: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    unmatched: list[str] = []
    if not failures:
        events = derive(normalized, subjects)
        matches, unmatched = pair(
            events, float(protocol["matching"]["point_estimate_window_ms"])
        )

    if analysis.get("schema") != "Fast-CAT/PILOT-001/independent-review-ingestion/v1.2":
        failures.append("ANALYSIS_SCHEMA_MISMATCH")
    if analysis.get("status") != "PASS":
        failures.append("ANALYSIS_REPORT_NOT_PASS")
    if analysis.get("completed_review_form_sha256") != form_sha:
        failures.append("ANALYSIS_FORM_SHA256_MISMATCH")
    if analysis.get("frame_manifest_file_sha256") != manifest_sha:
        failures.append("ANALYSIS_FRAME_MANIFEST_SHA256_MISMATCH")
    if analysis.get("reviewer_attestation_sha256") != canonical_sha256(attestation):
        failures.append("ANALYSIS_ATTESTATION_SHA256_MISMATCH")
    for field, key, code in (
        (
            "blinded_package_content_identity_file_sha256",
            "content_identity_file_sha256",
            "ANALYSIS_CONTENT_IDENTITY_FILE_SHA256_MISMATCH",
        ),
        (
            "blinded_package_manifest_sha256",
            "package_manifest_file_sha256",
            "ANALYSIS_PACKAGE_MANIFEST_SHA256_MISMATCH",
        ),
        (
            "blinded_package_files_payload_sha256",
            "files_payload_sha256",
            "ANALYSIS_FILES_PAYLOAD_SHA256_MISMATCH",
        ),
    ):
        if analysis.get(field) != expected.get(key):
            failures.append(code)
    if analysis.get("transport_independent_package_content_binding_established") is not True:
        failures.append("ANALYSIS_CONTENT_BINDING_NOT_ESTABLISHED")
    if analysis.get("normalized_review_rows_sha256") != canonical_sha256(normalized):
        failures.append("NORMALIZED_REVIEW_ROWS_SHA256_MISMATCH")
    if analysis.get("derived_onsets_sha256") != canonical_sha256(events):
        failures.append("DERIVED_ONSETS_SHA256_MISMATCH")
    if analysis.get("matches_sha256") != canonical_sha256(matches):
        failures.append("MATCHES_SHA256_MISMATCH")
    if analysis.get("derived_onsets") != events:
        failures.append("DERIVED_ONSETS_CONTENT_MISMATCH")
    if analysis.get("matches") != matches:
        failures.append("MATCHES_CONTENT_MISMATCH")
    if analysis.get("unmatched_signaller_event_ids") != unmatched:
        failures.append("UNMATCHED_EVENT_SET_MISMATCH")
    if analysis.get("independent_frame_level_estimate_established") is not False:
        failures.append("ANALYSIS_SELF_PROMOTED_FINAL_ESTIMATE")

    failures = sorted(set(failures))
    report = {
        "schema": "Fast-CAT/PILOT-001/independent-review-verifier/v1.1",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "review_form_sha256": form_sha,
        "frame_manifest_file_sha256": manifest_sha,
        "blinded_package_content_identity_file_sha256": expected.get(
            "content_identity_file_sha256"
        ),
        "blinded_package_manifest_sha256": expected.get(
            "package_manifest_file_sha256"
        ),
        "blinded_package_files_payload_sha256": expected.get("files_payload_sha256"),
        "normalized_review_rows_sha256_recomputed": canonical_sha256(normalized),
        "derived_onsets_count_recomputed": len(events),
        "derived_onsets_sha256_recomputed": canonical_sha256(events),
        "matches_count_recomputed": len(matches),
        "matches_sha256_recomputed": canonical_sha256(matches),
        "transport_independent_package_content_binding_replayed": not failures,
        "independent_replay_established": not failures,
        "independent_frame_level_estimate_established": False,
        "claim_ceiling": "Independent replay of canonical-package-bound submitted blinded labels, onset derivation and deterministic pairing only. Full PILOT_001 scientific admission remains separate.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
