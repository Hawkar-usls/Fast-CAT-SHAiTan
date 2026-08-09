#!/usr/bin/env python3
"""Normalize the pinned dual-ROI cat_detection probe.

This stage validates candidate 48-point structure, checks whether both fixed ROI
channels produce spatially distinct faces, renders full-rate overlays, and derives
face-box-normalized ear/eye/mouth geometry deltas for *triage only*.

No body score is treated as landmark confidence. No geometry delta is promoted to
a CatFACS action, action onset, mimicry event, or latency measurement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

REGION_INDICES = {
    "ears": list(range(22, 32)),
    "eyes": list(range(4, 12)) + list(range(36, 42)),
    "mouth": [16, 17, 46, 47],
}
ROI_COLORS = {
    "cat_A_tabby_left": (0, 220, 255),
    "cat_B_black_right": (255, 0, 180),
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


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def valid_face(det: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    face = det.get("face")
    if not isinstance(face, dict):
        return False, ["FACE_MISSING"]
    landmarks = face.get("landmarks")
    if not isinstance(landmarks, list) or len(landmarks) != 48:
        return False, ["LANDMARK_COUNT_NOT_48"]
    indices: list[int] = []
    for i, lm in enumerate(landmarks):
        if not isinstance(lm, dict):
            failures.append(f"LANDMARK_{i}_NOT_OBJECT")
            continue
        try:
            index = int(lm.get("index"))
        except (TypeError, ValueError):
            failures.append(f"LANDMARK_{i}_INDEX_INVALID")
            continue
        indices.append(index)
        if not finite_number(lm.get("x")) or not finite_number(lm.get("y")):
            failures.append(f"LANDMARK_{i}_NONFINITE")
    if sorted(indices) != list(range(48)):
        failures.append("LANDMARK_INDEX_SET_NOT_0_TO_47")

    bbox = face.get("bbox")
    if not isinstance(bbox, dict):
        failures.append("FACE_BBOX_MISSING")
    else:
        try:
            left = float(bbox["left"])
            top = float(bbox["top"])
            right = float(bbox["right"])
            bottom = float(bbox["bottom"])
            if not all(math.isfinite(v) for v in (left, top, right, bottom)):
                raise ValueError
            if right <= left or bottom <= top:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            failures.append("FACE_BBOX_INVALID")
    return not failures, failures


def face_center(det: dict[str, Any]) -> tuple[float, float]:
    b = det["face"]["bbox"]
    return (
        (float(b["left"]) + float(b["right"])) / 2.0,
        (float(b["top"]) + float(b["bottom"])) / 2.0,
    )


def normalized_landmarks(det: dict[str, Any]) -> list[tuple[float, float]]:
    b = det["face"]["bbox"]
    left, top = float(b["left"]), float(b["top"])
    width = float(b["right"]) - left
    height = float(b["bottom"]) - top
    if width <= 0 or height <= 0:
        raise ValueError("FACE_BBOX_NONPOSITIVE")
    ordered = sorted(det["face"]["landmarks"], key=lambda x: int(x["index"]))
    return [
        ((float(lm["x"]) - left) / width, (float(lm["y"]) - top) / height)
        for lm in ordered
    ]


def region_rms_delta(
    previous: list[tuple[float, float]],
    current: list[tuple[float, float]],
    indices: list[int],
) -> float:
    squared = []
    for i in indices:
        dx = current[i][0] - previous[i][0]
        dy = current[i][1] - previous[i][1]
        squared.append(dx * dx + dy * dy)
    return math.sqrt(sum(squared) / len(squared))


def draw_overlay(
    src: Path,
    dst: Path,
    channels: dict[str, dict[str, Any]],
    frame_status: str,
) -> None:
    image = Image.open(src).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for cat_id, det in channels.items():
        color = ROI_COLORS.get(cat_id, (255, 255, 0))
        b = det["face"]["bbox"]
        draw.rectangle(
            (b["left"], b["top"], b["right"], b["bottom"]),
            outline=color,
            width=3,
        )
        draw.text(
            (float(b["left"]) + 3, float(b["top"]) + 3),
            cat_id,
            fill=color,
            font=font,
        )
        for lm in det["face"]["landmarks"]:
            index = int(lm["index"])
            x, y = float(lm["x"]), float(lm["y"])
            radius = 3 if 22 <= index <= 31 else 2
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    draw.rectangle((0, 0, image.width, 22), fill=(255, 255, 255))
    draw.text((4, 5), frame_status, fill=(0, 0, 0), font=font)
    dst.parent.mkdir(parents=True, exist_ok=True)
    image.save(dst, format="PNG", optimize=False)


def make_sheets(
    entries: list[dict[str, Any]],
    overlay_dir: Path,
    sheet_dir: Path,
) -> list[dict[str, Any]]:
    columns, rows, thumb_w = 4, 5, 300
    per_page = columns * rows
    font = ImageFont.load_default()
    sheet_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []

    for page in range((len(entries) + per_page - 1) // per_page):
        chunk = entries[page * per_page : (page + 1) * per_page]
        thumbs: list[tuple[Image.Image, str]] = []
        tile_h = 0
        for entry in chunk:
            image = Image.open(overlay_dir / entry["overlay_filename"]).convert("RGB")
            ratio = thumb_w / image.width
            height = max(1, round(image.height * ratio))
            thumb = image.resize((thumb_w, height), Image.Resampling.LANCZOS)
            label = (
                f"f{entry['frame_index']:06d} PTS={entry['pts_s']} "
                f"{entry['identity_status']}"
            )
            thumbs.append((thumb, label))
            tile_h = max(tile_h, height + 24)

        canvas = Image.new("RGB", (columns * thumb_w, rows * tile_h), "white")
        draw = ImageDraw.Draw(canvas)
        for slot, (thumb, label) in enumerate(thumbs):
            x = (slot % columns) * thumb_w
            y = (slot // columns) * tile_h
            canvas.paste(thumb, (x, y))
            draw.text((x + 4, y + thumb.height + 4), label, fill="black", font=font)

        path = sheet_dir / f"full_rate_identity_sheet_{page + 1:02d}.png"
        canvas.save(path, format="PNG", optimize=False)
        records.append(
            {
                "page": page + 1,
                "filename": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "frame_indices": [x["frame_index"] for x in chunk],
            }
        )
    return records


def normalize(args: argparse.Namespace) -> dict[str, Any]:
    raw = json.loads(args.raw_probe.read_text(encoding="utf-8"))
    ledger = json.loads(args.frame_ledger.read_text(encoding="utf-8"))
    width = int(ledger["stream"]["width"])
    height = int(ledger["stream"]["height"])
    diagonal = math.hypot(width, height)
    pts_by_index = {
        int(x["frame_index"]): str(x["pts_s"]) for x in ledger["frame_pts"]
    }
    selected_by_index = {
        int(x["frame_index"]): x for x in ledger["selection"]["selected"]
    }

    failures: list[str] = []
    structural_rows: list[dict[str, Any]] = []
    frame_entries: list[dict[str, Any]] = []
    previous_vectors: dict[str, tuple[int, str, list[tuple[float, float]]]] = {}
    region_motion: list[dict[str, Any]] = []

    overlay_dir = args.out_dir / "overlays"
    sheet_dir = args.out_dir / "overlay_sheets"
    overlay_dir.mkdir(parents=True, exist_ok=True)

    expected_cat_ids = sorted(raw.get("roi_policy_normalized_xyxy", {}).keys())
    if expected_cat_ids != ["cat_A_tabby_left", "cat_B_black_right"]:
        failures.append("ROI_POLICY_CAT_IDS_UNEXPECTED")

    complete_distinct_frames = 0
    review_duplicate_frames = 0
    incomplete_frames = 0
    valid_channel_counts = {cat_id: 0 for cat_id in expected_cat_ids}

    for frame in sorted(raw.get("frames", []), key=lambda x: int(x["frame_index"])):
        frame_index = int(frame["frame_index"])
        filename = str(frame["filename"])
        if frame_index not in selected_by_index:
            failures.append(f"RAW_PROBE_FRAME_NOT_IN_LEDGER:{frame_index}")
            continue
        if filename != selected_by_index[frame_index]["png_filename"]:
            failures.append(f"RAW_PROBE_FILENAME_MISMATCH:{frame_index}")
        pts_s = pts_by_index[frame_index]

        channel_reports = {
            str(x.get("candidate_cat_id", "")): x for x in frame.get("roi_channels", [])
        }
        valid_channels: dict[str, dict[str, Any]] = {}
        invalid_details: list[dict[str, Any]] = []

        for cat_id in expected_cat_ids:
            channel = channel_reports.get(cat_id)
            if channel is None:
                invalid_details.append({"candidate_cat_id": cat_id, "failures": ["ROI_CHANNEL_MISSING"]})
                continue
            detections = channel.get("detections", [])
            if not isinstance(detections, list) or len(detections) != 1:
                invalid_details.append(
                    {
                        "candidate_cat_id": cat_id,
                        "failures": [f"DETECTION_COUNT_NOT_1:{len(detections) if isinstance(detections, list) else 'invalid'}"],
                    }
                )
                continue
            det = detections[0]
            ok, reasons = valid_face(det)
            if not ok:
                invalid_details.append({"candidate_cat_id": cat_id, "failures": reasons})
                continue
            valid_channels[cat_id] = det
            valid_channel_counts[cat_id] += 1

        identity_status = "INCOMPLETE_ROI_FACE_CHANNELS"
        center_distance_fraction = None
        if len(valid_channels) == 2:
            centers = [face_center(valid_channels[x]) for x in expected_cat_ids]
            center_distance_fraction = math.hypot(
                centers[0][0] - centers[1][0],
                centers[0][1] - centers[1][1],
            ) / diagonal
            if center_distance_fraction < 0.08:
                identity_status = "REVIEW_DUPLICATE_FACE_RISK"
                review_duplicate_frames += 1
            else:
                identity_status = "PASS_DISTINCT_ROI_CANDIDATES"
                complete_distinct_frames += 1
        else:
            incomplete_frames += 1

        for cat_id, det in valid_channels.items():
            ordered = sorted(det["face"]["landmarks"], key=lambda x: int(x["index"]))
            row = {
                "video_id": raw.get("source_id"),
                "frame_index": frame_index,
                "pts_s": pts_s,
                "candidate_cat_id": cat_id,
                "landmark_confidence": None,
                "face_bbox": det["face"]["bbox"],
                "landmarks": [[float(lm["x"]), float(lm["y"])] for lm in ordered],
                "landmark_types": [str(lm["type"]) for lm in ordered],
                "admission": "CANDIDATE_ONLY_NO_CALIBRATED_LANDMARK_CONFIDENCE",
            }
            structural_rows.append(row)

            current_vector = normalized_landmarks(det)
            previous = previous_vectors.get(cat_id)
            if previous is not None:
                prev_index, prev_pts, previous_vector = previous
                deltas = {
                    region: region_rms_delta(previous_vector, current_vector, indices)
                    for region, indices in REGION_INDICES.items()
                }
                region_motion.append(
                    {
                        "candidate_cat_id": cat_id,
                        "from_frame_index": prev_index,
                        "to_frame_index": frame_index,
                        "from_pts_s": prev_pts,
                        "to_pts_s": pts_s,
                        "delta_pts_ms": (float(pts_s) - float(prev_pts)) * 1000.0,
                        "normalized_rms_delta": deltas,
                        "admission": "TRIAGE_ONLY_NOT_CATFACS",
                    }
                )
            previous_vectors[cat_id] = (frame_index, pts_s, current_vector)

        overlay_filename = f"overlay_{filename}"
        draw_overlay(
            args.frame_dir / filename,
            overlay_dir / overlay_filename,
            valid_channels,
            identity_status,
        )
        frame_entries.append(
            {
                "frame_index": frame_index,
                "pts_s": pts_s,
                "filename": filename,
                "overlay_filename": overlay_filename,
                "valid_candidate_cat_ids": sorted(valid_channels),
                "identity_status": identity_status,
                "face_center_distance_fraction_of_frame_diagonal": center_distance_fraction,
                "invalid_details": invalid_details,
            }
        )

    selected_count = int(ledger["selection"]["selected_count"])
    if len(frame_entries) != selected_count:
        failures.append("PROCESSED_FRAME_COUNT_DIFFERS_FROM_LEDGER")

    ranked_motion: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for cat_id in expected_cat_ids:
        ranked_motion[cat_id] = {}
        cat_rows = [x for x in region_motion if x["candidate_cat_id"] == cat_id]
        for region in REGION_INDICES:
            ranked_motion[cat_id][region] = sorted(
                cat_rows,
                key=lambda x: float(x["normalized_rms_delta"][region]),
                reverse=True,
            )[:10]

    sheets = make_sheets(frame_entries, overlay_dir, sheet_dir)
    structural_digest = canonical_sha256(structural_rows)
    region_motion_digest = canonical_sha256(region_motion)
    coverage = (
        complete_distinct_frames / selected_count if selected_count else 0.0
    )

    result = {
        "schema": "Fast-CAT/PILOT-001/landmark-candidate-normalization/v1.1",
        "source_id": raw.get("source_id"),
        "backend": raw.get("backend"),
        "status": "PASS_CANDIDATE_ONLY" if not failures else "FAIL",
        "failures": failures,
        "selected_frames_expected": selected_count,
        "selected_frames_processed": len(frame_entries),
        "valid_channel_frame_counts": valid_channel_counts,
        "frames_with_two_spatially_distinct_roi_candidates": complete_distinct_frames,
        "frames_with_duplicate_face_risk": review_duplicate_frames,
        "frames_with_incomplete_roi_face_channels": incomplete_frames,
        "two_candidate_coverage_fraction": coverage,
        "candidate_identity_complete_all_frames": bool(frame_entries)
        and complete_distinct_frames == selected_count,
        "structural_landmark_rows": structural_rows,
        "structural_landmark_rows_sha256": structural_digest,
        "region_motion_rows": region_motion,
        "region_motion_rows_sha256": region_motion_digest,
        "top_region_motion_candidates": ranked_motion,
        "frames": frame_entries,
        "overlay_sheets": sheets,
        "admission": {
            "two_cat_identity": "CANDIDATE_ONLY_PENDING_FULL_RATE_FRAME_REVIEW",
            "landmark_structure_48": "CANDIDATE_ONLY",
            "landmark_accuracy": "NOT_ESTABLISHED",
            "landmark_confidence": "UNAVAILABLE_FROM_BACKEND_PUBLIC_RESULT",
            "ear_eye_mouth_motion": "TRIAGE_ONLY_NOT_CATFACS",
            "facial_action_onset": "NOT_ESTABLISHED",
            "delta_t": "NOT_ESTABLISHED",
            "independent_frame_level_estimate": "NOT_ESTABLISHED"
        },
        "claim_ceiling": "This result validates only pinned full-rate fixed-ROI candidate geometry, spatial distinctness and normalized motion triage. It does not establish landmark accuracy, CatFACS action onset, mimicry, or feline latency."
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "candidate_normalization.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "selected_frames_processed": result["selected_frames_processed"],
                "valid_channel_frame_counts": result["valid_channel_frame_counts"],
                "frames_with_two_spatially_distinct_roi_candidates": result["frames_with_two_spatially_distinct_roi_candidates"],
                "frames_with_duplicate_face_risk": result["frames_with_duplicate_face_risk"],
                "frames_with_incomplete_roi_face_channels": result["frames_with_incomplete_roi_face_channels"],
                "two_candidate_coverage_fraction": result["two_candidate_coverage_fraction"],
                "candidate_identity_complete_all_frames": result["candidate_identity_complete_all_frames"],
                "structural_landmark_rows_sha256": structural_digest,
                "region_motion_rows_sha256": region_motion_digest,
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
    raise SystemExit(0 if report["status"].startswith("PASS") else 1)
