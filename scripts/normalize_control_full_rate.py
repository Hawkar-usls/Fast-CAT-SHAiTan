#!/usr/bin/env python3
"""Normalize the full-rate PILOT_001 conflict-control dual-ROI probe.

Detector misses and duplicate-face-risk frames are preserved as a valid negative
candidate-coverage outcome. Only malformed lineage/probe structure is a pipeline
failure. Full adjacent-frame ear-motion triage is admitted only at 1218/1218
spatially distinct two-candidate coverage.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from fastcat.control_full_rate import classify_full_rate_control
from scripts.normalize_control_landmark_probe import (
    canonical_sha256,
    center,
    draw_overlay,
    make_sheets,
    valid_face,
)
from scripts.normalize_landmark_probe import (
    REGION_INDICES,
    normalized_landmarks,
    region_rms_delta,
)

EXPECTED_SOURCE_ID = "commons_tomcats_conflict_2020"
EXPECTED_FRAME_COUNT = 1218
EXPECTED_FRAME_PTS_SHA256 = (
    "8b4c3d6ca63485cfbec384fba1e3490f198474f1d8bdac218c98f053305cae46"
)
EXPECTED_CAT_IDS = ("cat_C_brown_left", "cat_D_gray_right")


def normalize(args: argparse.Namespace) -> dict[str, Any]:
    raw = json.loads(args.raw_probe.read_text(encoding="utf-8"))
    ledger = json.loads(args.frame_ledger.read_text(encoding="utf-8"))
    failures: list[str] = []

    if raw.get("schema") != "Fast-CAT/PILOT-001/control-full-rate-roi-raw-probe/v1.0":
        failures.append("RAW_SCHEMA_MISMATCH")
    if raw.get("source_id") != EXPECTED_SOURCE_ID:
        failures.append("RAW_SOURCE_ID_MISMATCH")
    if ledger.get("source_id") != EXPECTED_SOURCE_ID:
        failures.append("LEDGER_SOURCE_ID_MISMATCH")
    if int(ledger.get("frame_count", -1)) != EXPECTED_FRAME_COUNT:
        failures.append("LEDGER_FRAME_COUNT_MISMATCH")
    if ledger.get("frame_pts_sha256") != EXPECTED_FRAME_PTS_SHA256:
        failures.append("LEDGER_FRAME_PTS_SHA256_MISMATCH")

    selected = ledger.get("selection", {}).get("selected", [])
    selected_count = int(ledger.get("selection", {}).get("selected_count", -1))
    if selected_count != EXPECTED_FRAME_COUNT or len(selected) != EXPECTED_FRAME_COUNT:
        failures.append("FULL_RATE_SELECTION_COUNT_MISMATCH")

    raw_cat_ids = tuple(sorted(raw.get("roi_policy_normalized_xyxy", {}).keys()))
    if raw_cat_ids != tuple(sorted(EXPECTED_CAT_IDS)):
        failures.append("ROI_POLICY_CAT_IDS_UNEXPECTED")

    selected_by_index = {int(x["frame_index"]): x for x in selected}
    pts_by_index = {
        int(x["frame_index"]): str(x["pts_s"])
        for x in ledger.get("frame_pts", [])
    }
    raw_frames = sorted(raw.get("frames", []), key=lambda x: int(x["frame_index"]))
    if int(raw.get("frames_processed", -1)) != len(raw_frames):
        failures.append("RAW_FRAMES_PROCESSED_FIELD_MISMATCH")

    actual_indices = [int(x["frame_index"]) for x in raw_frames]
    if actual_indices != list(range(EXPECTED_FRAME_COUNT)):
        failures.append("RAW_FRAME_INDEX_SEQUENCE_MISMATCH")

    diagonal = math.hypot(
        int(ledger.get("stream", {}).get("width", 0)),
        int(ledger.get("stream", {}).get("height", 0)),
    )
    if diagonal <= 0:
        failures.append("FRAME_DIAGONAL_INVALID")

    structural_rows: list[dict[str, Any]] = []
    region_motion: list[dict[str, Any]] = []
    frame_entries: list[dict[str, Any]] = []
    previous_vectors: dict[str, tuple[int, str, list[tuple[float, float]]]] = {}
    valid_channel_counts = {cat_id: 0 for cat_id in EXPECTED_CAT_IDS}
    distinct_count = 0
    duplicate_count = 0
    incomplete_count = 0

    overlay_dir = args.out_dir / "overlays"
    sheet_dir = args.out_dir / "overlay_sheets"
    overlay_dir.mkdir(parents=True, exist_ok=True)

    for frame in raw_frames:
        idx = int(frame["frame_index"])
        filename = str(frame["filename"])
        selected_row = selected_by_index.get(idx)
        if selected_row is None:
            failures.append(f"PROBE_FRAME_NOT_IN_LEDGER:{idx}")
            continue
        if filename != selected_row.get("png_filename"):
            failures.append(f"FRAME_FILENAME_MISMATCH:{idx}")
        if idx not in pts_by_index:
            failures.append(f"PTS_MISSING:{idx}")
            continue
        pts_s = pts_by_index[idx]

        channel_reports = {
            str(x.get("candidate_cat_id", "")): x
            for x in frame.get("roi_channels", [])
        }
        valid: dict[str, dict[str, Any]] = {}
        invalid_details: list[dict[str, Any]] = []
        for cat_id in EXPECTED_CAT_IDS:
            channel = channel_reports.get(cat_id)
            if channel is None:
                invalid_details.append(
                    {"candidate_cat_id": cat_id, "failures": ["ROI_CHANNEL_MISSING"]}
                )
                continue
            detections = channel.get("detections", [])
            if not isinstance(detections, list) or len(detections) != 1:
                invalid_details.append(
                    {
                        "candidate_cat_id": cat_id,
                        "failures": [
                            "DETECTION_COUNT_NOT_1:"
                            + str(len(detections) if isinstance(detections, list) else "invalid")
                        ],
                    }
                )
                continue
            det = detections[0]
            ok, reasons = valid_face(det)
            if not ok:
                invalid_details.append(
                    {"candidate_cat_id": cat_id, "failures": reasons}
                )
                continue
            valid[cat_id] = det
            valid_channel_counts[cat_id] += 1

        frame_status = "INCOMPLETE_ROI_FACE_CHANNELS"
        center_distance_fraction = None
        if len(valid) == 2:
            a, b = [center(valid[x]) for x in EXPECTED_CAT_IDS]
            center_distance_fraction = math.hypot(a[0] - b[0], a[1] - b[1]) / diagonal
            if center_distance_fraction >= 0.08:
                frame_status = "PASS_DISTINCT_ROI_CANDIDATES"
                distinct_count += 1
            else:
                frame_status = "REVIEW_DUPLICATE_FACE_RISK"
                duplicate_count += 1
        else:
            incomplete_count += 1

        for cat_id, det in valid.items():
            ordered = sorted(
                det["face"]["landmarks"], key=lambda x: int(x["index"])
            )
            structural_rows.append(
                {
                    "video_id": EXPECTED_SOURCE_ID,
                    "frame_index": idx,
                    "pts_s": pts_s,
                    "candidate_cat_id": cat_id,
                    "landmark_confidence": None,
                    "face_bbox": det["face"]["bbox"],
                    "landmarks": [
                        [float(lm["x"]), float(lm["y"])] for lm in ordered
                    ],
                    "landmark_types": [str(lm.get("type", "")) for lm in ordered],
                    "admission": "CANDIDATE_ONLY_NO_CALIBRATED_LANDMARK_CONFIDENCE",
                }
            )

            current_vector = normalized_landmarks(det)
            previous = previous_vectors.get(cat_id)
            if previous is not None and previous[0] + 1 == idx:
                prev_index, prev_pts, previous_vector = previous
                deltas = {
                    region: region_rms_delta(previous_vector, current_vector, indices)
                    for region, indices in REGION_INDICES.items()
                }
                region_motion.append(
                    {
                        "candidate_cat_id": cat_id,
                        "from_frame_index": prev_index,
                        "to_frame_index": idx,
                        "from_pts_s": prev_pts,
                        "to_pts_s": pts_s,
                        "delta_pts_ms": (float(pts_s) - float(prev_pts)) * 1000.0,
                        "normalized_rms_delta": deltas,
                        "admission": "TRIAGE_ONLY_NOT_CATFACS",
                    }
                )
            previous_vectors[cat_id] = (idx, pts_s, current_vector)

        overlay_filename = f"overlay_{filename}"
        draw_overlay(
            args.frame_dir / filename,
            overlay_dir / overlay_filename,
            valid,
            frame_status,
        )
        frame_entries.append(
            {
                "frame_index": idx,
                "pts_s": pts_s,
                "filename": filename,
                "overlay_filename": overlay_filename,
                "status": frame_status,
                "valid_candidate_cat_ids": sorted(valid),
                "face_center_distance_fraction_of_frame_diagonal": center_distance_fraction,
                "invalid_details": invalid_details,
            }
        )

    classification = classify_full_rate_control(
        expected_frames=EXPECTED_FRAME_COUNT,
        processed_frames=len(frame_entries),
        distinct_two_candidate_frames=distinct_count,
        duplicate_face_risk_frames=duplicate_count,
        incomplete_roi_frames=incomplete_count,
        integrity_failures=failures,
    )

    ranked_motion: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for cat_id in EXPECTED_CAT_IDS:
        ranked_motion[cat_id] = {}
        cat_rows = [x for x in region_motion if x["candidate_cat_id"] == cat_id]
        for region in REGION_INDICES:
            ranked_motion[cat_id][region] = sorted(
                cat_rows,
                key=lambda x: float(x["normalized_rms_delta"][region]),
                reverse=True,
            )[:10]

    sheets = make_sheets(frame_entries, overlay_dir, sheet_dir)
    result = {
        "schema": "Fast-CAT/PILOT-001/landmark-candidate-normalization/v1.1",
        "source_id": EXPECTED_SOURCE_ID,
        "control_gate_schema": "Fast-CAT/PILOT-001/control-full-rate-normalization/v1.0",
        "backend": raw.get("backend"),
        "status": classification["status"],
        "scientific_outcome": classification["scientific_outcome"],
        "failures": classification["failures"],
        "selected_frames_expected": EXPECTED_FRAME_COUNT,
        "selected_frames_processed": len(frame_entries),
        "valid_channel_frame_counts": valid_channel_counts,
        "frames_with_two_spatially_distinct_roi_candidates": distinct_count,
        "frames_with_duplicate_face_risk": duplicate_count,
        "frames_with_incomplete_roi_face_channels": incomplete_count,
        "two_candidate_coverage_fraction": classification["coverage_fraction"],
        "candidate_identity_complete_all_frames": classification[
            "adjacent_full_rate_ear_triage_admitted"
        ],
        "adjacent_full_rate_ear_triage_admitted": classification[
            "adjacent_full_rate_ear_triage_admitted"
        ],
        "structural_landmark_rows": structural_rows,
        "structural_landmark_rows_sha256": canonical_sha256(structural_rows),
        "region_motion_rows": region_motion,
        "region_motion_rows_sha256": canonical_sha256(region_motion),
        "top_region_motion_candidates": ranked_motion,
        "frames": frame_entries,
        "overlay_sheets": sheets,
        "admission": {
            "full_rate_control_candidate_coverage": (
                "ESTABLISHED_CANDIDATE_ONLY"
                if classification["adjacent_full_rate_ear_triage_admitted"]
                else "INCOMPLETE_VALID_NEGATIVE"
            ),
            "two_cat_identity": "CANDIDATE_ONLY_NOT_INDEPENDENT_IDENTITY",
            "landmark_structure_48": "CANDIDATE_ONLY",
            "landmark_accuracy": "NOT_ESTABLISHED",
            "landmark_confidence": "UNAVAILABLE_FROM_BACKEND_PUBLIC_RESULT",
            "ear_eye_mouth_motion": "TRIAGE_ONLY_NOT_CATFACS",
            "facial_action_onset": "NOT_ESTABLISHED",
            "delta_t": "NOT_ESTABLISHED",
            "independent_frame_level_estimate": "NOT_ESTABLISHED",
        },
        "claim_ceiling": "This full-rate control result establishes only the observed pinned fixed-ROI candidate-geometry coverage and associated deterministic motion triage availability. It does not establish landmark accuracy, independent cat identity, CatFACS EAD103/EAD104, action onset, mimicry, delta-t, feline latency or INDEPENDENT_FRAME_LEVEL_ESTIMATE.",
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / "candidate_normalization.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": result["status"],
                "scientific_outcome": result["scientific_outcome"],
                "selected_frames_processed": result["selected_frames_processed"],
                "frames_with_two_spatially_distinct_roi_candidates": distinct_count,
                "frames_with_duplicate_face_risk": duplicate_count,
                "frames_with_incomplete_roi_face_channels": incomplete_count,
                "two_candidate_coverage_fraction": result[
                    "two_candidate_coverage_fraction"
                ],
                "adjacent_full_rate_ear_triage_admitted": result[
                    "adjacent_full_rate_ear_triage_admitted"
                ],
                "structural_landmark_rows_sha256": result[
                    "structural_landmark_rows_sha256"
                ],
                "region_motion_rows_sha256": result["region_motion_rows_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-probe", required=True, type=Path)
    parser.add_argument("--frame-ledger", required=True, type=Path)
    parser.add_argument("--frame-dir", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    report = normalize(parse_args())
    raise SystemExit(1 if report["status"] == "FAIL" else 0)
