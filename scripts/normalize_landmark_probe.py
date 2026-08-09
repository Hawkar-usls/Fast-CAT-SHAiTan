#!/usr/bin/env python3
"""Normalize a pinned cat_detection probe into candidate-only Fast-CAT evidence.

Important: this script does NOT convert body detection confidence into landmark
confidence. It validates the structure of 48-point outputs, builds a deterministic
sampled-frame identity candidate by geometry continuity, and renders overlays for
human review. Nothing here admits CatFACS action onset or delta-t.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


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
    seen_indices: list[int] = []
    for i, lm in enumerate(landmarks):
        if not isinstance(lm, dict):
            failures.append(f"LANDMARK_{i}_NOT_OBJECT")
            continue
        try:
            index = int(lm.get("index"))
        except (TypeError, ValueError):
            failures.append(f"LANDMARK_{i}_INDEX_INVALID")
            continue
        seen_indices.append(index)
        if not finite_number(lm.get("x")) or not finite_number(lm.get("y")):
            failures.append(f"LANDMARK_{i}_NONFINITE")
    if sorted(seen_indices) != list(range(48)):
        failures.append("LANDMARK_INDEX_SET_NOT_0_TO_47")
    return not failures, failures


def bbox_center(box: dict[str, Any]) -> tuple[float, float]:
    return (
        (float(box["left"]) + float(box["right"])) / 2.0,
        (float(box["top"]) + float(box["bottom"])) / 2.0,
    )


def bbox_iou(a: dict[str, Any], b: dict[str, Any]) -> float:
    left = max(float(a["left"]), float(b["left"]))
    top = max(float(a["top"]), float(b["top"]))
    right = min(float(a["right"]), float(b["right"]))
    bottom = min(float(a["bottom"]), float(b["bottom"]))
    inter = max(0.0, right - left) * max(0.0, bottom - top)
    area_a = max(0.0, float(a["right"]) - float(a["left"])) * max(0.0, float(a["bottom"]) - float(a["top"]))
    area_b = max(0.0, float(b["right"]) - float(b["left"])) * max(0.0, float(b["bottom"]) - float(b["top"]))
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def track_cost(prev: dict[str, Any], cur: dict[str, Any], diag: float) -> float:
    p = bbox_center(prev["body_bbox"])
    c = bbox_center(cur["body_bbox"])
    distance = math.hypot(c[0] - p[0], c[1] - p[1]) / diag
    return distance + 0.5 * (1.0 - bbox_iou(prev["body_bbox"], cur["body_bbox"]))


def choose_initial(valid: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    top = sorted(valid, key=lambda d: (-float(d.get("body_score", 0.0)), int(d.get("detection_index", 0))))[:2]
    top.sort(key=lambda d: bbox_center(d["body_bbox"])[0])
    return {"cat_A": top[0], "cat_B": top[1]}


def choose_next(
    prev: dict[str, dict[str, Any]],
    valid: list[dict[str, Any]],
    diag: float,
) -> tuple[dict[str, dict[str, Any]] | None, float | None]:
    if len(valid) < 2:
        return None, None
    best: dict[str, dict[str, Any]] | None = None
    best_cost: float | None = None
    for a, b in itertools.permutations(valid, 2):
        cost = track_cost(prev["cat_A"], a, diag) + track_cost(prev["cat_B"], b, diag)
        key = (cost, int(a.get("detection_index", 0)), int(b.get("detection_index", 0)))
        if best_cost is None or key < (
            best_cost,
            int(best["cat_A"].get("detection_index", 0)),
            int(best["cat_B"].get("detection_index", 0)),
        ):
            best_cost = cost
            best = {"cat_A": a, "cat_B": b}
    return best, best_cost


def draw_overlay(
    src: Path,
    dst: Path,
    assignments: dict[str, dict[str, Any]] | None,
    unassigned: list[dict[str, Any]],
) -> None:
    image = Image.open(src).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    palette = {"cat_A": (0, 220, 255), "cat_B": (255, 0, 180)}

    if assignments:
        for cat_id, det in assignments.items():
            color = palette[cat_id]
            body = det["body_bbox"]
            face = det["face"]["bbox"]
            draw.rectangle((body["left"], body["top"], body["right"], body["bottom"]), outline=color, width=4)
            draw.rectangle((face["left"], face["top"], face["right"], face["bottom"]), outline=color, width=2)
            draw.text((float(body["left"]) + 4, float(body["top"]) + 4), cat_id, fill=color, font=font)
            for lm in det["face"]["landmarks"]:
                x = float(lm["x"])
                y = float(lm["y"])
                r = 3 if 22 <= int(lm["index"]) <= 31 else 2
                draw.ellipse((x - r, y - r, x + r, y + r), fill=color)

    for det in unassigned:
        body = det.get("body_bbox")
        if isinstance(body, dict):
            draw.rectangle((body["left"], body["top"], body["right"], body["bottom"]), outline=(120, 120, 120), width=2)

    dst.parent.mkdir(parents=True, exist_ok=True)
    image.save(dst, format="PNG", optimize=False)


def make_sheets(entries: list[dict[str, Any]], overlay_dir: Path, sheet_dir: Path) -> list[dict[str, Any]]:
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
            im = Image.open(overlay_dir / entry["overlay_filename"]).convert("RGB")
            ratio = thumb_w / im.width
            h = max(1, round(im.height * ratio))
            thumb = im.resize((thumb_w, h), Image.Resampling.LANCZOS)
            label = f"f{entry['frame_index']:06d} PTS={entry['pts_s']}  {entry['identity_status']}"
            thumbs.append((thumb, label))
            tile_h = max(tile_h, h + 24)
        canvas = Image.new("RGB", (columns * thumb_w, rows * tile_h), "white")
        draw = ImageDraw.Draw(canvas)
        for slot, (thumb, label) in enumerate(thumbs):
            x = (slot % columns) * thumb_w
            y = (slot // columns) * tile_h
            canvas.paste(thumb, (x, y))
            draw.text((x + 4, y + thumb.height + 4), label, fill="black", font=font)
        path = sheet_dir / f"candidate_identity_sheet_{page + 1:02d}.png"
        canvas.save(path, format="PNG", optimize=False)
        records.append({"page": page + 1, "filename": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return records


def normalize(args: argparse.Namespace) -> dict[str, Any]:
    raw = json.loads(args.raw_probe.read_text(encoding="utf-8"))
    ledger = json.loads(args.frame_ledger.read_text(encoding="utf-8"))
    width = int(ledger["stream"]["width"])
    height = int(ledger["stream"]["height"])
    diag = math.hypot(width, height)
    pts_by_index = {int(x["frame_index"]): str(x["pts_s"]) for x in ledger["frame_pts"]}
    selected_by_index = {int(x["frame_index"]): x for x in ledger["selection"]["selected"]}

    failures: list[str] = []
    structural_rows: list[dict[str, Any]] = []
    frame_entries: list[dict[str, Any]] = []
    prev: dict[str, dict[str, Any]] | None = None
    first_anchor_index: int | None = None
    max_tracking_cost = 0.0
    frames_with_two_valid = 0
    frames_with_any_valid = 0

    overlay_dir = args.out_dir / "overlays"
    sheet_dir = args.out_dir / "overlay_sheets"
    overlay_dir.mkdir(parents=True, exist_ok=True)

    for frame in sorted(raw.get("frames", []), key=lambda x: int(x["frame_index"])):
        frame_index = int(frame["frame_index"])
        filename = str(frame["filename"])
        if frame_index not in selected_by_index:
            failures.append(f"RAW_PROBE_FRAME_NOT_IN_LEDGER:{frame_index}")
            continue
        if filename != selected_by_index[frame_index]["png_filename"]:
            failures.append(f"RAW_PROBE_FILENAME_MISMATCH:{frame_index}")
        pts_s = pts_by_index[frame_index]

        valid: list[dict[str, Any]] = []
        invalid_face_details: list[dict[str, Any]] = []
        for det in frame.get("detections", []):
            ok, reasons = valid_face(det)
            if ok:
                valid.append(det)
            elif det.get("face") is not None:
                invalid_face_details.append({"detection_index": det.get("detection_index"), "failures": reasons})

        if valid:
            frames_with_any_valid += 1
        if len(valid) >= 2:
            frames_with_two_valid += 1

        assignments: dict[str, dict[str, Any]] | None = None
        tracking_cost: float | None = None
        identity_status = "NO_TWO_VALID_FACES"
        if prev is None and len(valid) >= 2:
            assignments = choose_initial(valid)
            prev = assignments
            first_anchor_index = frame_index
            identity_status = "INITIAL_LEFT_RIGHT_ANCHOR"
        elif prev is not None and len(valid) >= 2:
            assignments, tracking_cost = choose_next(prev, valid, diag)
            if assignments is not None:
                prev = assignments
                max_tracking_cost = max(max_tracking_cost, float(tracking_cost or 0.0))
                identity_status = "GEOMETRIC_CONTINUITY_CANDIDATE"

        assigned_indices = set()
        if assignments:
            for cat_id, det in assignments.items():
                assigned_indices.add(int(det["detection_index"]))
                structural_rows.append({
                    "video_id": raw.get("source_id"),
                    "frame_index": frame_index,
                    "pts_s": pts_s,
                    "candidate_cat_id": cat_id,
                    "backend_detection_index": int(det["detection_index"]),
                    "body_score": det.get("body_score"),
                    "landmark_confidence": None,
                    "body_bbox": det["body_bbox"],
                    "face_bbox": det["face"]["bbox"],
                    "landmarks": [[float(lm["x"]), float(lm["y"])] for lm in sorted(det["face"]["landmarks"], key=lambda x: int(x["index"]))],
                    "landmark_types": [str(lm["type"]) for lm in sorted(det["face"]["landmarks"], key=lambda x: int(x["index"]))],
                    "admission": "CANDIDATE_ONLY_NO_CALIBRATED_LANDMARK_CONFIDENCE",
                })

        unassigned = [det for det in valid if int(det["detection_index"]) not in assigned_indices]
        overlay_filename = f"overlay_{filename}"
        draw_overlay(args.frame_dir / filename, overlay_dir / overlay_filename, assignments, unassigned)
        frame_entries.append({
            "frame_index": frame_index,
            "pts_s": pts_s,
            "filename": filename,
            "overlay_filename": overlay_filename,
            "raw_detection_count": int(frame.get("detection_count", 0)),
            "valid_48_face_count": len(valid),
            "invalid_face_details": invalid_face_details,
            "identity_status": identity_status,
            "tracking_cost": tracking_cost,
            "assigned_detection_indices": None if assignments is None else {k: int(v["detection_index"]) for k, v in assignments.items()},
        })

    sheets = make_sheets(frame_entries, overlay_dir, sheet_dir)
    selected_count = int(ledger["selection"]["selected_count"])
    frame_fraction_two = frames_with_two_valid / selected_count if selected_count else 0.0
    structural_payload_sha256 = canonical_sha256(structural_rows)

    result = {
        "schema": "Fast-CAT/PILOT-001/landmark-candidate-normalization/v1.0",
        "source_id": raw.get("source_id"),
        "backend": raw.get("backend"),
        "status": "PASS_CANDIDATE_ONLY" if not failures else "FAIL",
        "failures": failures,
        "selected_frames_expected": selected_count,
        "selected_frames_processed": len(frame_entries),
        "frames_with_any_valid_48_face": frames_with_any_valid,
        "frames_with_at_least_two_valid_48_faces": frames_with_two_valid,
        "fraction_with_at_least_two_valid_48_faces": frame_fraction_two,
        "first_two_cat_anchor_frame_index": first_anchor_index,
        "max_sampled_tracking_cost": max_tracking_cost,
        "candidate_identity_complete_on_sampled_frames": bool(frame_entries) and all(e["assigned_detection_indices"] is not None for e in frame_entries),
        "structural_landmark_rows": structural_rows,
        "structural_landmark_rows_sha256": structural_payload_sha256,
        "frames": frame_entries,
        "overlay_sheets": sheets,
        "admission": {
            "two_cat_identity": "CANDIDATE_ONLY_PENDING_FRAME_REVIEW",
            "landmark_structure_48": "CANDIDATE_ONLY",
            "landmark_accuracy": "NOT_ESTABLISHED",
            "landmark_confidence": "UNAVAILABLE_FROM_BACKEND_PUBLIC_RESULT",
            "facial_action_onset": "NOT_ESTABLISHED",
            "delta_t": "NOT_ESTABLISHED",
            "independent_frame_level_estimate": "NOT_ESTABLISHED"
        },
        "claim_ceiling": "This result validates only the structure and continuity of a pinned external detector's candidate outputs on sampled frames. It does not establish landmark accuracy, CatFACS action onset, mimicry, or feline latency."
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "candidate_normalization.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ["status", "selected_frames_processed", "frames_with_at_least_two_valid_48_faces", "fraction_with_at_least_two_valid_48_faces", "first_two_cat_anchor_frame_index", "candidate_identity_complete_on_sampled_frames", "structural_landmark_rows_sha256"]}, indent=2, sort_keys=True))
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
    raise SystemExit(0 if report["status"].startswith("PASS") else 1)
