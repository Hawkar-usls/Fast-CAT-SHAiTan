#!/usr/bin/env python3
"""Build a full-rate, face-aligned ear-motion triage ledger.

This is a model-development aid only. It removes a best-fit 2D similarity motion
estimated from non-ear facial landmarks, then measures residual motion of each
ear relative to the face. Every adjacent decoded-frame transition is preserved.
No threshold turns geometry into CatFACS; ranking only changes review order.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

RIGHT_EAR = tuple(range(22, 27))
LEFT_EAR = tuple(range(27, 32))
NON_EAR_ANCHORS = tuple(i for i in range(48) if i not in range(22, 32))
IOD_PAIR = (4, 8)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _point(value: Any) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("POINT_INVALID")
    x, y = float(value[0]), float(value[1])
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("POINT_NONFINITE")
    return x, y


def validate_landmarks(value: Any) -> list[tuple[float, float]]:
    if not isinstance(value, list) or len(value) != 48:
        raise ValueError("LANDMARK_COUNT_NOT_48")
    return [_point(p) for p in value]


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def fit_similarity(
    source: list[tuple[float, float]],
    target: list[tuple[float, float]],
    indices: tuple[int, ...] = NON_EAR_ANCHORS,
) -> dict[str, float]:
    """Least-squares orientation-preserving 2D similarity: source -> target.

    The transform is:
      x' = c*x - s*y + tx
      y' = s*x + c*y + ty
    where scale=sqrt(c^2+s^2).
    """
    if len(source) != 48 or len(target) != 48:
        raise ValueError("EXPECTED_48_POINTS")
    if len(indices) < 2:
        raise ValueError("TOO_FEW_ANCHORS")

    sx = sum(source[i][0] for i in indices) / len(indices)
    sy = sum(source[i][1] for i in indices) / len(indices)
    txm = sum(target[i][0] for i in indices) / len(indices)
    tym = sum(target[i][1] for i in indices) / len(indices)

    denom = 0.0
    a = 0.0
    b = 0.0
    for i in indices:
        ux = source[i][0] - sx
        uy = source[i][1] - sy
        vx = target[i][0] - txm
        vy = target[i][1] - tym
        denom += ux * ux + uy * uy
        a += ux * vx + uy * vy
        b += ux * vy - uy * vx
    if denom <= 1e-12:
        raise ValueError("DEGENERATE_ANCHOR_GEOMETRY")

    c = a / denom
    ss = b / denom
    scale = math.hypot(c, ss)
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("SIMILARITY_SCALE_INVALID")

    trans_x = txm - (c * sx - ss * sy)
    trans_y = tym - (ss * sx + c * sy)
    return {
        "c": c,
        "s": ss,
        "tx": trans_x,
        "ty": trans_y,
        "scale": scale,
        "rotation_rad": math.atan2(ss, c),
    }


def apply_similarity(
    points: list[tuple[float, float]],
    transform: dict[str, float],
) -> list[tuple[float, float]]:
    c = float(transform["c"])
    s = float(transform["s"])
    tx = float(transform["tx"])
    ty = float(transform["ty"])
    return [
        (c * x - s * y + tx, s * x + c * y + ty)
        for x, y in points
    ]


def rms_residual(
    target: list[tuple[float, float]],
    aligned_source: list[tuple[float, float]],
    indices: tuple[int, ...],
) -> float:
    values = []
    for i in indices:
        dx = aligned_source[i][0] - target[i][0]
        dy = aligned_source[i][1] - target[i][1]
        values.append(dx * dx + dy * dy)
    return math.sqrt(sum(values) / len(values))


def centroid(
    points: list[tuple[float, float]],
    indices: tuple[int, ...],
) -> tuple[float, float]:
    return (
        sum(points[i][0] for i in indices) / len(indices),
        sum(points[i][1] for i in indices) / len(indices),
    )


def transition_metrics(
    previous: list[tuple[float, float]],
    current: list[tuple[float, float]],
) -> dict[str, Any]:
    transform = fit_similarity(current, previous)
    aligned_current = apply_similarity(current, transform)

    iod = distance(previous[IOD_PAIR[0]], previous[IOD_PAIR[1]])
    if iod <= 1e-9:
        raise ValueError("INTEROCULAR_DISTANCE_INVALID")

    anchor_px = rms_residual(previous, aligned_current, NON_EAR_ANCHORS)
    right_px = rms_residual(previous, aligned_current, RIGHT_EAR)
    left_px = rms_residual(previous, aligned_current, LEFT_EAR)

    prev_right_center = centroid(previous, RIGHT_EAR)
    prev_left_center = centroid(previous, LEFT_EAR)
    cur_right_center = centroid(aligned_current, RIGHT_EAR)
    cur_left_center = centroid(aligned_current, LEFT_EAR)

    right_vector = (
        (cur_right_center[0] - prev_right_center[0]) / iod,
        (cur_right_center[1] - prev_right_center[1]) / iod,
    )
    left_vector = (
        (cur_left_center[0] - prev_left_center[0]) / iod,
        (cur_left_center[1] - prev_left_center[1]) / iod,
    )

    anchor = anchor_px / iod
    right = right_px / iod
    left = left_px / iod
    right_excess = max(0.0, right - anchor)
    left_excess = max(0.0, left - anchor)
    return {
        "interocular_distance_px": iod,
        "similarity_transform_current_to_previous": transform,
        "anchor_rms_iod": anchor,
        "right_ear_rms_iod": right,
        "left_ear_rms_iod": left,
        "right_ear_excess_over_anchor_iod": right_excess,
        "left_ear_excess_over_anchor_iod": left_excess,
        "max_ear_excess_over_anchor_iod": max(right_excess, left_excess),
        "right_ear_centroid_delta_iod": [right_vector[0], right_vector[1]],
        "left_ear_centroid_delta_iod": [left_vector[0], left_vector[1]],
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    source = json.loads(args.candidate_normalization.read_text(encoding="utf-8"))
    if source.get("schema") != "Fast-CAT/PILOT-001/landmark-candidate-normalization/v1.1":
        raise RuntimeError("CANDIDATE_NORMALIZATION_SCHEMA_MISMATCH")
    if source.get("status") != "PASS_CANDIDATE_ONLY":
        raise RuntimeError("CANDIDATE_NORMALIZATION_NOT_PASS_CANDIDATE_ONLY")
    if source.get("candidate_identity_complete_all_frames") is not True:
        raise RuntimeError("FULL_RATE_CANDIDATE_IDENTITY_INCOMPLETE")

    rows = source.get("structural_landmark_rows", [])
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        cat_id = str(row.get("candidate_cat_id", ""))
        if not cat_id:
            raise RuntimeError("CANDIDATE_CAT_ID_MISSING")
        by_cat.setdefault(cat_id, []).append(row)

    transitions: list[dict[str, Any]] = []
    expected_frame_count = int(source.get("selected_frames_processed", 0))
    if expected_frame_count <= 1:
        raise RuntimeError("TOO_FEW_FRAMES")

    for cat_id, cat_rows in sorted(by_cat.items()):
        cat_rows.sort(key=lambda x: int(x["frame_index"]))
        if len(cat_rows) != expected_frame_count:
            raise RuntimeError(f"FULL_RATE_ROWS_MISSING:{cat_id}:{len(cat_rows)}")
        expected_indices = list(range(expected_frame_count))
        actual_indices = [int(x["frame_index"]) for x in cat_rows]
        if actual_indices != expected_indices:
            raise RuntimeError(f"FRAME_INDEX_SEQUENCE_MISMATCH:{cat_id}")

        for previous_row, current_row in zip(cat_rows, cat_rows[1:]):
            previous = validate_landmarks(previous_row["landmarks"])
            current = validate_landmarks(current_row["landmarks"])
            metrics = transition_metrics(previous, current)
            from_pts = float(previous_row["pts_s"])
            to_pts = float(current_row["pts_s"])
            if not (to_pts > from_pts):
                raise RuntimeError(f"PTS_NOT_STRICT:{cat_id}:{current_row['frame_index']}")
            transitions.append(
                {
                    "candidate_cat_id": cat_id,
                    "from_frame_index": int(previous_row["frame_index"]),
                    "to_frame_index": int(current_row["frame_index"]),
                    "from_pts_s": from_pts,
                    "to_pts_s": to_pts,
                    "delta_pts_ms": (to_pts - from_pts) * 1000.0,
                    **metrics,
                    "admission": "TRIAGE_ONLY_NOT_CATFACS",
                }
            )

    expected_transition_count = (expected_frame_count - 1) * len(by_cat)
    if len(transitions) != expected_transition_count:
        raise RuntimeError(
            f"TRANSITION_COUNT_MISMATCH:{len(transitions)}!={expected_transition_count}"
        )

    rankings: dict[str, list[dict[str, Any]]] = {}
    for cat_id in sorted(by_cat):
        cat_transitions = [x for x in transitions if x["candidate_cat_id"] == cat_id]
        ranked = sorted(
            cat_transitions,
            key=lambda x: (
                -float(x["max_ear_excess_over_anchor_iod"]),
                int(x["from_frame_index"]),
            ),
        )
        rankings[cat_id] = [
            {
                "rank": rank,
                "from_frame_index": row["from_frame_index"],
                "to_frame_index": row["to_frame_index"],
                "from_pts_s": row["from_pts_s"],
                "to_pts_s": row["to_pts_s"],
                "anchor_rms_iod": row["anchor_rms_iod"],
                "right_ear_rms_iod": row["right_ear_rms_iod"],
                "left_ear_rms_iod": row["left_ear_rms_iod"],
                "right_ear_excess_over_anchor_iod": row[
                    "right_ear_excess_over_anchor_iod"
                ],
                "left_ear_excess_over_anchor_iod": row[
                    "left_ear_excess_over_anchor_iod"
                ],
                "max_ear_excess_over_anchor_iod": row[
                    "max_ear_excess_over_anchor_iod"
                ],
            }
            for rank, row in enumerate(ranked, start=1)
        ]

    payload_digest = canonical_sha256(transitions)
    ranking_digest = canonical_sha256(rankings)
    report = {
        "schema": "Fast-CAT/PILOT-001/ear-motion-triage/v1.0",
        "source_id": source.get("source_id"),
        "candidate_normalization_sha256": canonical_sha256(source),
        "landmark_anchor_indices": list(NON_EAR_ANCHORS),
        "right_ear_indices": list(RIGHT_EAR),
        "left_ear_indices": list(LEFT_EAR),
        "normalization_scale": "previous-frame landmark 4-to-8 interocular distance",
        "alignment": "least-squares orientation-preserving 2D similarity fitted current->previous on all non-ear landmarks",
        "transition_count": len(transitions),
        "transitions": transitions,
        "transitions_sha256": payload_digest,
        "rankings": rankings,
        "rankings_sha256": ranking_digest,
        "review_policy": {
            "all_transitions_preserved": True,
            "rank_only_changes_debug_review_order": True,
            "rank_is_not_action_probability": True,
            "no_threshold_creates_EAD103_or_EAD104": True,
            "final_independent_action_reviewer_must_not_see_this_ranking_before_labels_are_frozen": True,
        },
        "admission": {
            "face_aligned_ear_motion": "ESTABLISHED_AS_DETERMINISTIC_GEOMETRIC_TRIAGE_ONLY",
            "EAD103": "NOT_ESTABLISHED",
            "EAD104": "NOT_ESTABLISHED",
            "facial_action_onset": "NOT_ESTABLISHED",
            "delta_t": "NOT_ESTABLISHED",
            "independent_frame_level_estimate": "NOT_ESTABLISHED",
        },
        "claim_ceiling": "The report ranks deterministic residual ear geometry after non-ear facial similarity alignment. It does not validate landmark accuracy, identify CatFACS actions, establish action onset, or measure feline reaction latency.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "PASS_TRIAGE_ONLY",
                "transition_count": len(transitions),
                "transitions_sha256": payload_digest,
                "rankings_sha256": ranking_digest,
                "top5": {
                    cat: rows[:5] for cat, rows in rankings.items()
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-normalization", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    build(parse_args())
