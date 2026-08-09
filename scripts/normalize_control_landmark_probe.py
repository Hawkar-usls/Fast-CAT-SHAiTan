#!/usr/bin/env python3
"""Normalize the sampled PILOT_001 conflict-control dual-ROI landmark probe."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

EXPECTED_CAT_IDS = ("cat_C_brown_left", "cat_D_gray_right")
COLORS = {
    "cat_C_brown_left": (0, 220, 255),
    "cat_D_gray_right": (255, 0, 180),
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def valid_face(det: dict[str, Any]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    face = det.get("face")
    if not isinstance(face, dict):
        return False, ["FACE_MISSING"]
    landmarks = face.get("landmarks")
    if not isinstance(landmarks, list) or len(landmarks) != 48:
        failures.append("LANDMARK_COUNT_NOT_48")
        return False, failures
    indices = []
    for i, lm in enumerate(landmarks):
        if not isinstance(lm, dict):
            failures.append(f"LANDMARK_{i}_NOT_OBJECT")
            continue
        try:
            idx = int(lm["index"])
            x = float(lm["x"])
            y = float(lm["y"])
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError
            indices.append(idx)
        except (KeyError, TypeError, ValueError):
            failures.append(f"LANDMARK_{i}_INVALID")
    if sorted(indices) != list(range(48)):
        failures.append("LANDMARK_INDEX_SET_NOT_0_TO_47")
    bbox = face.get("bbox")
    if not isinstance(bbox, dict):
        failures.append("FACE_BBOX_MISSING")
    else:
        try:
            l, t, r, b = [float(bbox[k]) for k in ("left", "top", "right", "bottom")]
            if not all(math.isfinite(x) for x in (l, t, r, b)) or r <= l or b <= t:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            failures.append("FACE_BBOX_INVALID")
    return not failures, failures


def center(det: dict[str, Any]) -> tuple[float, float]:
    b = det["face"]["bbox"]
    return ((float(b["left"]) + float(b["right"])) / 2.0, (float(b["top"]) + float(b["bottom"])) / 2.0)


def draw_overlay(src: Path, dst: Path, valid: dict[str, dict[str, Any]], status: str) -> None:
    image = Image.open(src).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.rectangle((0, 0, image.width, 22), fill=(255, 255, 255))
    draw.text((4, 5), status, fill=(0, 0, 0), font=font)
    for cat_id, det in valid.items():
        color = COLORS[cat_id]
        bbox = det["face"]["bbox"]
        draw.rectangle((bbox["left"], bbox["top"], bbox["right"], bbox["bottom"]), outline=color, width=3)
        draw.text((float(bbox["left"]) + 3, float(bbox["top"]) + 3), cat_id, fill=color, font=font)
        for lm in det["face"]["landmarks"]:
            idx = int(lm["index"])
            x, y = float(lm["x"]), float(lm["y"])
            radius = 3 if 22 <= idx <= 31 else 2
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    dst.parent.mkdir(parents=True, exist_ok=True)
    image.save(dst, format="PNG", optimize=False)


def make_sheets(entries: list[dict[str, Any]], overlay_dir: Path, sheet_dir: Path) -> list[dict[str, Any]]:
    columns, rows, thumb_w = 4, 5, 300
    per_page = columns * rows
    font = ImageFont.load_default()
    sheet_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for page in range((len(entries) + per_page - 1) // per_page):
        chunk = entries[page * per_page:(page + 1) * per_page]
        thumbs = []
        tile_h = 0
        for entry in chunk:
            im = Image.open(overlay_dir / entry["overlay_filename"]).convert("RGB")
            ratio = thumb_w / im.width
            h = max(1, round(im.height * ratio))
            thumb = im.resize((thumb_w, h), Image.Resampling.LANCZOS)
            thumbs.append((thumb, f"f{entry['frame_index']:06d} {entry['status']}"))
            tile_h = max(tile_h, h + 24)
        canvas = Image.new("RGB", (columns * thumb_w, rows * tile_h), "white")
        draw = ImageDraw.Draw(canvas)
        for slot, (thumb, label) in enumerate(thumbs):
            x = (slot % columns) * thumb_w
            y = (slot // columns) * tile_h
            canvas.paste(thumb, (x, y))
            draw.text((x + 4, y + thumb.height + 4), label, fill="black", font=font)
        path = sheet_dir / f"control_candidate_sheet_{page + 1:02d}.png"
        canvas.save(path, format="PNG", optimize=False)
        out.append({"page": page + 1, "filename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return out


def normalize(args: argparse.Namespace) -> dict[str, Any]:
    raw = json.loads(args.raw_probe.read_text(encoding="utf-8"))
    ledger = json.loads(args.frame_ledger.read_text(encoding="utf-8"))
    if raw.get("schema") != "Fast-CAT/PILOT-001/control-roi-raw-probe/v1.0":
        raise RuntimeError("RAW_SCHEMA_MISMATCH")
    if ledger.get("source_id") != raw.get("source_id"):
        raise RuntimeError("SOURCE_ID_MISMATCH")
    selected = ledger["selection"]["selected"]
    if len(selected) != 83:
        raise RuntimeError(f"EXPECTED_83_SELECTED_FRAMES:{len(selected)}")
    selected_by_index = {int(x["frame_index"]): x for x in selected}
    pts_by_index = {int(x["frame_index"]): str(x["pts_s"]) for x in ledger["frame_pts"]}
    diag = math.hypot(int(ledger["stream"]["width"]), int(ledger["stream"]["height"]))

    frames = []
    structural_rows = []
    pass_count = review_count = 0
    channel_valid = {x: 0 for x in EXPECTED_CAT_IDS}
    overlay_dir = args.out_dir / "overlays"
    sheet_dir = args.out_dir / "overlay_sheets"

    for frame in sorted(raw.get("frames", []), key=lambda x: int(x["frame_index"])):
        idx = int(frame["frame_index"])
        if idx not in selected_by_index:
            raise RuntimeError(f"PROBE_FRAME_NOT_IN_LEDGER:{idx}")
        if frame["filename"] != selected_by_index[idx]["png_filename"]:
            raise RuntimeError(f"FILENAME_MISMATCH:{idx}")
        channels = {str(x.get("candidate_cat_id", "")): x for x in frame.get("roi_channels", [])}
        valid = {}
        failures = []
        for cat_id in EXPECTED_CAT_IDS:
            ch = channels.get(cat_id)
            if ch is None:
                failures.append(f"{cat_id}:CHANNEL_MISSING")
                continue
            detections = ch.get("detections", [])
            if not isinstance(detections, list) or len(detections) != 1:
                failures.append(f"{cat_id}:DETECTION_COUNT_{len(detections) if isinstance(detections, list) else 'INVALID'}")
                continue
            det = detections[0]
            ok, why = valid_face(det)
            if not ok:
                failures.extend(f"{cat_id}:{x}" for x in why)
                continue
            valid[cat_id] = det
            channel_valid[cat_id] += 1
            structural_rows.append({
                "source_id": raw.get("source_id"),
                "frame_index": idx,
                "pts_s": pts_by_index[idx],
                "candidate_cat_id": cat_id,
                "face_bbox": det["face"]["bbox"],
                "landmarks": [[float(x["x"]), float(x["y"])] for x in sorted(det["face"]["landmarks"], key=lambda x: int(x["index"]))],
                "landmark_confidence": None,
                "admission": "CANDIDATE_ONLY"
            })
        status = "REVIEW"
        center_distance_fraction = None
        if len(valid) == 2:
            a, b = [center(valid[x]) for x in EXPECTED_CAT_IDS]
            center_distance_fraction = math.hypot(a[0] - b[0], a[1] - b[1]) / diag
            if center_distance_fraction >= 0.08:
                status = "PASS_CANDIDATE_ONLY"
                pass_count += 1
            else:
                failures.append("DUPLICATE_FACE_RISK")
                review_count += 1
        else:
            review_count += 1
        overlay_filename = f"overlay_{frame['filename']}"
        draw_overlay(args.frame_dir / frame["filename"], overlay_dir / overlay_filename, valid, status)
        frames.append({
            "frame_index": idx,
            "pts_s": pts_by_index[idx],
            "filename": frame["filename"],
            "overlay_filename": overlay_filename,
            "status": status,
            "valid_candidate_cat_ids": sorted(valid),
            "face_center_distance_fraction_of_frame_diagonal": center_distance_fraction,
            "failures": failures
        })

    if len(frames) != 83:
        raise RuntimeError(f"PROCESSED_COUNT_MISMATCH:{len(frames)}")
    sheets = make_sheets(frames, overlay_dir, sheet_dir)
    result = {
        "schema": "Fast-CAT/PILOT-001/control-landmark-preflight-result/v1.0",
        "source_id": raw.get("source_id"),
        "status": "PASS_CANDIDATE_ONLY" if pass_count > 0 else "NO_FEASIBLE_TWO_FACE_SAMPLE",
        "sampled_frames": len(frames),
        "pass_candidate_frames": pass_count,
        "review_frames": review_count,
        "pass_candidate_fraction": pass_count / len(frames),
        "valid_channel_frame_counts": channel_valid,
        "structural_rows": structural_rows,
        "structural_rows_sha256": canonical_sha256(structural_rows),
        "frames": frames,
        "overlay_sheets": sheets,
        "admission": {
            "sampled_two_cat_roi_coverage": "CANDIDATE_ONLY",
            "landmark_structure_48": "CANDIDATE_ONLY",
            "landmark_accuracy": "NOT_ESTABLISHED",
            "facial_action_onset": "NOT_ESTABLISHED",
            "delta_t": "NOT_ESTABLISHED",
            "full_rate_control_gate": "NOT_STARTED"
        },
        "claim_ceiling": "A positive result establishes sampled control feasibility only. It does not establish final identity, landmark accuracy, CatFACS action onset, mimicry, or latency."
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "control_candidate_normalization.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "sampled_frames": result["sampled_frames"],
        "pass_candidate_frames": result["pass_candidate_frames"],
        "review_frames": result["review_frames"],
        "pass_candidate_fraction": result["pass_candidate_fraction"],
        "valid_channel_frame_counts": result["valid_channel_frame_counts"],
        "structural_rows_sha256": result["structural_rows_sha256"]
    }, indent=2, sort_keys=True))
    return result


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--raw-probe", required=True, type=Path)
    p.add_argument("--frame-ledger", required=True, type=Path)
    p.add_argument("--frame-dir", required=True, type=Path)
    p.add_argument("--out-dir", required=True, type=Path)
    return p.parse_args()


if __name__ == "__main__":
    report = normalize(parse_args())
    raise SystemExit(0 if report["status"] == "PASS_CANDIDATE_ONLY" else 1)
