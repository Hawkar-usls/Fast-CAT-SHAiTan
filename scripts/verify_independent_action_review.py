#!/usr/bin/env python3
"""Independently replay a completed PILOT_001 blinded-review ingestion.

This verifier intentionally does not import fastcat.review_ingestion or the
analysis CLI. It independently checks package lineage, CSV/attestation fields,
derives ABSENT->PRESENT onsets, replays deterministic cross-subject matching,
and compares canonical SHA-256 identities with the analysis report.
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
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def derive(rows: list[dict[str, Any]], subjects: list[str]) -> list[dict[str, Any]]:
    by_subject = {subject: [] for subject in subjects}
    for row in rows:
        by_subject[row["subject_id"]].append(row)
    events: list[dict[str, Any]] = []
    for subject in subjects:
        seq = sorted(by_subject[subject], key=lambda x: x["frame_index"])
        for previous, current in zip(seq, seq[1:]):
            if current["frame_index"] != previous["frame_index"] + 1:
                raise RuntimeError(f"NON_ADJACENT_ROWS:{subject}")
            if previous["identity_confirmed"] != "yes" or current["identity_confirmed"] != "yes":
                continue
            for channel, (action, laterality) in CHANNELS.items():
                if previous[channel] == "ABSENT" and current[channel] == "PRESENT":
                    index = current["frame_index"]
                    events.append({
                        "event_id": f"{subject}:{action}:{laterality}:f{index:06d}",
                        "source_id": current["source_id"],
                        "subject_id": subject,
                        "action": action,
                        "laterality": laterality,
                        "previous_absent_frame_index": previous["frame_index"],
                        "previous_absent_pts_s": float(previous["pts_s"]),
                        "onset_frame_index": index,
                        "onset_pts_s": float(current["pts_s"]),
                        "event_source": "manual_catfacs_frame_review",
                        "review_state_transition": "ABSENT->PRESENT",
                    })
    return sorted(events, key=lambda x: (x["onset_pts_s"], x["subject_id"], x["action"], x["laterality"], x["event_id"]))


def interval(signaller: dict[str, Any], responder: dict[str, Any]) -> dict[str, float]:
    sp = float(signaller["previous_absent_pts_s"])
    s = float(signaller["onset_pts_s"])
    rp = float(responder["previous_absent_pts_s"])
    r = float(responder["onset_pts_s"])
    if not (0 <= sp < s <= r and 0 <= rp < r):
        raise RuntimeError("EVENT_PTS_BRACKET_INVALID")
    point = (r - s) * 1000.0
    lower = (rp - s) * 1000.0
    upper = (r - sp) * 1000.0
    return {
        "point_ms": point,
        "lower_ms": lower,
        "upper_ms": upper,
        "signaller_bracket_ms": (s - sp) * 1000.0,
        "responder_bracket_ms": (r - rp) * 1000.0,
        "interval_width_ms": upper - lower,
    }


def pair(events: list[dict[str, Any]], window_ms: float) -> tuple[list[dict[str, Any]], list[str]]:
    ordered = sorted(events, key=lambda x: (float(x["onset_pts_s"]), x["event_id"]))
    used_responses: set[str] = set()
    matched_signallers: set[str] = set()
    matches = []
    for signaller in ordered:
        chosen = None
        for responder in ordered:
            if responder["event_id"] == signaller["event_id"]:
                continue
            if responder["event_id"] in used_responses:
                continue
            if responder["subject_id"] == signaller["subject_id"]:
                continue
            if responder["action"] != signaller["action"]:
                continue
            dt_ms = (float(responder["onset_pts_s"]) - float(signaller["onset_pts_s"])) * 1000.0
            if 0.0 <= dt_ms <= window_ms:
                chosen = responder
                break
        if chosen is None:
            continue
        iv = interval(signaller, chosen)
        used_responses.add(chosen["event_id"])
        matched_signallers.add(signaller["event_id"])
        matches.append({
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
            "latency_ms": iv["point_ms"],
            "acquisition_interval_ms": iv,
            "interval_boundary_ambiguous": iv["lower_ms"] < 0.0 or iv["upper_ms"] > window_ms,
        })
    unmatched = [event["event_id"] for event in ordered if event["event_id"] not in matched_signallers]
    return matches, unmatched


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--frame-manifest", required=True, type=Path)
    parser.add_argument("--review-form", required=True, type=Path)
    parser.add_argument("--attestation", required=True, type=Path)
    parser.add_argument("--analysis-report", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    manifest = json.loads(args.frame_manifest.read_text(encoding="utf-8"))
    attestation = json.loads(args.attestation.read_text(encoding="utf-8"))
    analysis = json.loads(args.analysis_report.read_text(encoding="utf-8"))
    expected = protocol["expected_blinded_package"]
    failures: list[str] = []

    manifest_file_sha = sha256_file(args.frame_manifest)
    form_sha = sha256_file(args.review_form)
    if manifest_file_sha != expected["frame_manifest_file_sha256"]:
        failures.append("FRAME_MANIFEST_FILE_SHA256_NOT_FROZEN_PACKAGE")
    if manifest.get("source_id") != protocol["source_id"]:
        failures.append("FRAME_MANIFEST_SOURCE_MISMATCH")
    if manifest.get("raw_media_sha256") != expected["raw_media_sha256"]:
        failures.append("FRAME_MANIFEST_RAW_SHA256_MISMATCH")
    if manifest.get("frame_pts_sha256") != expected["frame_pts_sha256"]:
        failures.append("FRAME_MANIFEST_PTS_SHA256_MISMATCH")
    if int(manifest.get("frame_count", -1)) != int(expected["decoded_frame_count"]):
        failures.append("FRAME_MANIFEST_COUNT_MISMATCH")
    if manifest.get("contains_model_derived_fields") is not False:
        failures.append("FRAME_MANIFEST_MODEL_FIELDS_FLAG_INVALID")

    if attestation.get("schema") != "Fast-CAT/PILOT-001/reviewer-attestation/v1.0":
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
    if attestation.get("blinded_package_artifact_digest") != expected["workflow_artifact_digest"]:
        failures.append("ATTESTATION_PACKAGE_DIGEST_MISMATCH")
    if attestation.get("blank_review_form_sha256") != expected["blank_review_form_sha256"]:
        failures.append("ATTESTATION_BLANK_FORM_SHA256_MISMATCH")

    frames = manifest.get("frames", [])
    frame_by_index = {}
    last_pts = None
    for position, frame in enumerate(frames):
        try:
            index = int(frame["frame_index"])
            pts = float(frame["pts_s"])
            if index != position or not math.isfinite(pts) or pts < 0:
                raise ValueError
            if last_pts is not None and pts <= last_pts:
                raise ValueError
            last_pts = pts
            frame_by_index[index] = frame
        except (KeyError, TypeError, ValueError):
            failures.append(f"FRAME_{position}:INVALID_SEQUENCE_OR_PTS")

    with args.review_form.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if list(reader.fieldnames or []) != HEADERS:
            failures.append("REVIEW_HEADERS_MISMATCH_OR_MODEL_FIELDS_PRESENT")
        raw_rows = list(reader)
    if len(raw_rows) != int(expected["expected_annotation_rows"]):
        failures.append("REVIEW_ROW_COUNT_MISMATCH")

    subjects = list(expected["subjects"])
    allowed_states = set(protocol["allowed_review_states"])
    allowed_identity = set(protocol["allowed_identity_states"])
    expected_pairs = [(i, s) for i in range(int(expected["decoded_frame_count"])) for s in subjects]
    actual_pairs = []
    normalized = []
    for row_number, row in enumerate(raw_rows):
        try:
            index = int(row["frame_index"])
        except (KeyError, TypeError, ValueError):
            failures.append(f"ROW_{row_number}:FRAME_INDEX_INVALID")
            continue
        subject = str(row.get("subject_id", ""))
        actual_pairs.append((index, subject))
        frame = frame_by_index.get(index)
        if frame is None:
            failures.append(f"ROW_{row_number}:FRAME_MISSING")
            continue
        if row.get("source_id") != protocol["source_id"]:
            failures.append(f"ROW_{row_number}:SOURCE_ID_MISMATCH")
        if subject not in subjects:
            failures.append(f"ROW_{row_number}:SUBJECT_INVALID")
        if str(row.get("pts_s")) != str(frame.get("pts_s")):
            failures.append(f"ROW_{row_number}:PTS_MISMATCH")
        identity = str(row.get("identity_confirmed", ""))
        if identity not in allowed_identity:
            failures.append(f"ROW_{row_number}:IDENTITY_INVALID")
        state_values = {}
        for channel in CHANNELS:
            state = str(row.get(channel, ""))
            state_values[channel] = state
            if state not in allowed_states:
                failures.append(f"ROW_{row_number}:{channel}:STATE_INVALID")
        normalized.append({
            "source_id": str(row.get("source_id", "")),
            "frame_index": index,
            "pts_s": str(frame.get("pts_s")),
            "subject_id": subject,
            "identity_confirmed": identity,
            **state_values,
            "review_notes": str(row.get("review_notes", "")),
        })
    if actual_pairs != expected_pairs:
        failures.append("REVIEW_ORDER_OR_COVERAGE_MISMATCH")

    events: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    unmatched: list[str] = []
    if not failures:
        events = derive(normalized, subjects)
        matches, unmatched = pair(events, float(protocol["matching"]["point_estimate_window_ms"]))

    if analysis.get("status") != "PASS":
        failures.append("ANALYSIS_REPORT_NOT_PASS")
    if analysis.get("completed_review_form_sha256") != form_sha:
        failures.append("ANALYSIS_FORM_SHA256_MISMATCH")
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

    report = {
        "schema": "Fast-CAT/PILOT-001/independent-review-verifier/v1.0",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "review_form_sha256": form_sha,
        "frame_manifest_file_sha256": manifest_file_sha,
        "normalized_review_rows_sha256_recomputed": canonical_sha256(normalized),
        "derived_onsets_count_recomputed": len(events),
        "derived_onsets_sha256_recomputed": canonical_sha256(events),
        "matches_count_recomputed": len(matches),
        "matches_sha256_recomputed": canonical_sha256(matches),
        "independent_replay_established": not failures,
        "independent_frame_level_estimate_established": False,
        "claim_ceiling": "Independent replay of submitted blinded labels, onset derivation and deterministic pairing only. Full PILOT_001 scientific admission remains separate."
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
