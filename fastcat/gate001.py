from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def parse_rate(value: str | int | float | None) -> float:
    if value in (None, "", "0/0"):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError):
        return 0.0


def first_video_stream(ffprobe: dict[str, Any]) -> dict[str, Any]:
    for stream in ffprobe.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream
    raise ValueError("FFPROBE_VIDEO_STREAM_MISSING")


def timing_descriptor(ffprobe: dict[str, Any]) -> dict[str, Any]:
    stream = first_video_stream(ffprobe)
    avg_fps = parse_rate(stream.get("avg_frame_rate"))
    nominal_fps = parse_rate(stream.get("r_frame_rate"))
    fps = avg_fps or nominal_fps
    if fps <= 0:
        raise ValueError("FPS_UNAVAILABLE")

    time_base = str(stream.get("time_base") or "")
    time_base_s = parse_rate(time_base)
    if time_base_s <= 0:
        raise ValueError("TIME_BASE_UNAVAILABLE")

    duration_raw = stream.get("duration")
    if duration_raw in (None, ""):
        duration_raw = ffprobe.get("format", {}).get("duration")
    duration_s = float(duration_raw) if duration_raw not in (None, "") else None

    return {
        "codec_name": stream.get("codec_name"),
        "width": int(stream.get("width", 0)),
        "height": int(stream.get("height", 0)),
        "avg_frame_rate": str(stream.get("avg_frame_rate", "")),
        "r_frame_rate": str(stream.get("r_frame_rate", "")),
        "effective_fps": fps,
        "frame_interval_ms_nominal": 1000.0 / fps,
        "time_base": time_base,
        "time_base_us": time_base_s * 1_000_000.0,
        "duration_s": duration_s,
        "nb_frames": stream.get("nb_frames"),
    }


def validate_source_receipt(receipt: dict[str, Any], manifest_source: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if receipt.get("source_id") != manifest_source.get("source_id"):
        failures.append("SOURCE_ID_MISMATCH")
    if receipt.get("source_page") != manifest_source.get("source_page"):
        failures.append("SOURCE_PAGE_MISMATCH")
    if receipt.get("source_license") != manifest_source.get("license"):
        failures.append("SOURCE_LICENSE_MISMATCH")

    digest = str(receipt.get("raw_media_sha256", ""))
    if not SHA256_RE.fullmatch(digest):
        failures.append("RAW_SHA256_INVALID")
    if int(receipt.get("byte_length", 0)) <= 0:
        failures.append("RAW_BYTE_LENGTH_INVALID")

    probe = receipt.get("ffprobe")
    if not isinstance(probe, dict):
        failures.append("FFPROBE_MISSING")
        return failures
    try:
        timing = timing_descriptor(probe)
    except (TypeError, ValueError):
        failures.append("TIMING_METADATA_INVALID")
        return failures

    expected_w = int(manifest_source.get("width_px", 0) or 0)
    expected_h = int(manifest_source.get("height_px", 0) or 0)
    if expected_w and timing["width"] != expected_w:
        failures.append("WIDTH_MISMATCH")
    if expected_h and timing["height"] != expected_h:
        failures.append("HEIGHT_MISMATCH")

    expected_duration = manifest_source.get("duration_s")
    if expected_duration is not None and timing["duration_s"] is not None:
        if abs(float(expected_duration) - float(timing["duration_s"])) > 0.25:
            failures.append("DURATION_MISMATCH")
    return failures


def validate_landmark_rows(rows: Iterable[dict[str, Any]], *, expected_landmarks: int = 48, min_confidence: float = 0.5) -> tuple[list[str], dict[str, Any]]:
    failures: list[str] = []
    rows = list(rows)
    if not rows:
        return ["LANDMARK_ROWS_EMPTY"], {}

    by_video_cat: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    cat_ids_by_video: dict[str, set[str]] = defaultdict(set)

    for i, row in enumerate(rows):
        prefix = f"ROW_{i}"
        video_id = str(row.get("video_id", ""))
        cat_id = str(row.get("cat_id", ""))
        if not video_id:
            failures.append(f"{prefix}:VIDEO_ID_MISSING")
        if not cat_id:
            failures.append(f"{prefix}:CAT_ID_MISSING")

        landmarks = row.get("landmarks")
        if not isinstance(landmarks, list) or len(landmarks) != expected_landmarks:
            failures.append(f"{prefix}:LANDMARK_COUNT_NOT_{expected_landmarks}")
        else:
            for j, point in enumerate(landmarks):
                if not isinstance(point, (list, tuple)) or len(point) != 2 or not all(isinstance(v, (int, float)) and math.isfinite(float(v)) for v in point):
                    failures.append(f"{prefix}:LANDMARK_{j}_INVALID")
                    break

        try:
            pts_s = float(row["pts_s"])
            if not math.isfinite(pts_s) or pts_s < 0:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            failures.append(f"{prefix}:PTS_INVALID")
            pts_s = float("nan")

        try:
            confidence = float(row.get("confidence", 0.0))
            if not math.isfinite(confidence) or confidence < min_confidence or confidence > 1.0:
                failures.append(f"{prefix}:CONFIDENCE_OUT_OF_RANGE")
        except (TypeError, ValueError):
            failures.append(f"{prefix}:CONFIDENCE_INVALID")

        if video_id and cat_id and math.isfinite(pts_s):
            by_video_cat[(video_id, cat_id)].append(row)
            cat_ids_by_video[video_id].add(cat_id)

    for key, seq in by_video_cat.items():
        times = [float(x["pts_s"]) for x in seq]
        if any(b <= a for a, b in zip(times, times[1:])):
            failures.append(f"PTS_NOT_STRICTLY_INCREASING:{key[0]}:{key[1]}")
    for video_id, cat_ids in cat_ids_by_video.items():
        if len(cat_ids) < 2:
            failures.append(f"TWO_CAT_IDENTITY_NOT_ESTABLISHED:{video_id}")

    return failures, {
        "rows": len(rows),
        "videos": sorted(cat_ids_by_video),
        "cat_ids_by_video": {k: sorted(v) for k, v in sorted(cat_ids_by_video.items())},
    }


def validate_event_rows(events: Iterable[dict[str, Any]], *, allowed_actions: set[str], allowed_sources: set[str], min_confidence: float) -> tuple[list[str], list[dict[str, Any]]]:
    failures: list[str] = []
    events = list(events)
    ids: set[str] = set()
    for i, event in enumerate(events):
        prefix = f"EVENT_{i}"
        event_id = str(event.get("event_id", ""))
        if not event_id:
            failures.append(f"{prefix}:EVENT_ID_MISSING")
        elif event_id in ids:
            failures.append(f"{prefix}:EVENT_ID_DUPLICATE")
        ids.add(event_id)
        if str(event.get("action", "")) not in allowed_actions:
            failures.append(f"{prefix}:ACTION_NOT_PREREGISTERED")
        if str(event.get("source", "")) not in allowed_sources:
            failures.append(f"{prefix}:EVENT_SOURCE_NOT_ALLOWED")
        try:
            confidence = float(event.get("confidence", 0.0))
            if confidence < min_confidence or confidence > 1.0 or not math.isfinite(confidence):
                failures.append(f"{prefix}:EVENT_CONFIDENCE_BELOW_GATE")
        except (TypeError, ValueError):
            failures.append(f"{prefix}:EVENT_CONFIDENCE_INVALID")
        try:
            onset = float(event["onset_pts_s"])
            if onset < 0 or not math.isfinite(onset):
                raise ValueError
        except (KeyError, TypeError, ValueError):
            failures.append(f"{prefix}:ONSET_PTS_INVALID")
        if not str(event.get("video_id", "")):
            failures.append(f"{prefix}:VIDEO_ID_MISSING")
        if not str(event.get("cat_id", "")):
            failures.append(f"{prefix}:CAT_ID_MISSING")
    events.sort(key=lambda x: (str(x.get("video_id", "")), float(x.get("onset_pts_s", 0)), str(x.get("event_id", ""))))
    return failures, events


def deterministic_matches(events: Iterable[dict[str, Any]], *, window_ms: float) -> list[dict[str, Any]]:
    """Earliest unused same-action response by the other cat within the frozen forward window."""
    events = sorted(list(events), key=lambda x: (str(x["video_id"]), float(x["onset_pts_s"]), str(x["event_id"])))
    window_s = window_ms / 1000.0
    used_responses: set[str] = set()
    matches: list[dict[str, Any]] = []
    for i, signaller in enumerate(events):
        best = None
        best_dt = None
        for responder in events[i + 1:]:
            if responder["video_id"] != signaller["video_id"]:
                if responder["video_id"] > signaller["video_id"]:
                    break
                continue
            if responder["event_id"] in used_responses or responder["cat_id"] == signaller["cat_id"] or responder["action"] != signaller["action"]:
                continue
            dt = float(responder["onset_pts_s"]) - float(signaller["onset_pts_s"])
            if dt < 0:
                continue
            if dt > window_s:
                break
            best, best_dt = responder, dt
            break
        if best is not None and best_dt is not None:
            used_responses.add(str(best["event_id"]))
            matches.append({
                "video_id": signaller["video_id"],
                "action": signaller["action"],
                "signaller_event_id": signaller["event_id"],
                "responder_event_id": best["event_id"],
                "signaller_cat_id": signaller["cat_id"],
                "responder_cat_id": best["cat_id"],
                "signaller_pts_s": float(signaller["onset_pts_s"]),
                "responder_pts_s": float(best["onset_pts_s"]),
                "latency_ms": best_dt * 1000.0,
            })
    return matches


def summarize_matches(matches: Iterable[dict[str, Any]]) -> dict[str, Any]:
    vals = [float(m["latency_ms"]) for m in matches]
    if not vals:
        return {"n_matches": 0, "latencies_ms": [], "mean_ms": None, "median_ms": None, "min_ms": None, "max_ms": None}
    return {
        "n_matches": len(vals), "latencies_ms": vals,
        "mean_ms": statistics.mean(vals), "median_ms": statistics.median(vals),
        "min_ms": min(vals), "max_ms": max(vals),
    }


def latency_quantization_bound_ms(source_timings: Iterable[dict[str, Any]]) -> float:
    intervals = [float(x["frame_interval_ms_nominal"]) for x in source_timings]
    if not intervals:
        raise ValueError("SOURCE_TIMINGS_EMPTY")
    return max(intervals)


def gate_report(*, source_receipts: list[dict[str, Any]], manifest_sources: dict[str, dict[str, Any]], protocol: dict[str, Any], landmark_rows: list[dict[str, Any]] | None = None, event_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    failures: list[str] = []
    source_timings: list[dict[str, Any]] = []
    expected_source_ids = list(protocol["sources"])
    receipt_by_id = {str(x.get("source_id", "")): x for x in source_receipts}
    if sorted(receipt_by_id) != sorted(expected_source_ids):
        failures.append("SOURCE_SET_DIFFERS_FROM_PREREGISTRATION")

    for source_id in expected_source_ids:
        rec, man = receipt_by_id.get(source_id), manifest_sources.get(source_id)
        if rec is None or man is None:
            failures.append(f"SOURCE_MISSING:{source_id}")
            continue
        failures.extend(f"{source_id}:{x}" for x in validate_source_receipt(rec, man))
        if isinstance(rec.get("ffprobe"), dict):
            try:
                source_timings.append(timing_descriptor(rec["ffprobe"]))
            except ValueError:
                pass

    stages = {
        "open_video": not any("SOURCE_" in x and ("MISSING" in x or "MISMATCH" in x) for x in failures),
        "raw_sha256": all(SHA256_RE.fullmatch(str(receipt_by_id.get(s, {}).get("raw_media_sha256", ""))) for s in expected_source_ids),
        "pts_fps": len(source_timings) == len(expected_source_ids),
        "landmarks_48": False,
        "facial_action_onset": False,
        "delta_t": False,
    }

    landmark_meta: dict[str, Any] = {}
    if landmark_rows is not None:
        lm_failures, landmark_meta = validate_landmark_rows(landmark_rows, expected_landmarks=int(protocol["landmark_count"]), min_confidence=float(protocol["min_landmark_confidence"]))
        failures.extend(lm_failures)
        stages["landmarks_48"] = not lm_failures

    matches: list[dict[str, Any]] = []
    summary = summarize_matches(matches)
    if event_rows is not None:
        allowed_actions = set(protocol["primary_actions"]) | set(protocol["secondary_actions"])
        ev_failures, clean_events = validate_event_rows(event_rows, allowed_actions=allowed_actions, allowed_sources=set(protocol["allowed_event_sources"]), min_confidence=float(protocol["min_event_confidence"]))
        failures.extend(ev_failures)
        stages["facial_action_onset"] = not ev_failures and bool(clean_events)
        if stages["landmarks_48"] and stages["facial_action_onset"]:
            matches = deterministic_matches(clean_events, window_ms=float(protocol["rapid_mimicry_window_ms"]))
            summary = summarize_matches(matches)
            stages["delta_t"] = True

    quantization_bound = latency_quantization_bound_ms(source_timings) if len(source_timings) == len(expected_source_ids) else None
    all_measurement_gates = all(stages.values())
    independent_estimate = bool(all_measurement_gates and protocol.get("analysis_frozen_before_measurement") is True and protocol.get("selection_policy") == "all_eligible_events_no_posthoc_dropping")
    return {
        "schema": "Fast-CAT/GATE-001/v1.0",
        "stages": stages,
        "failures": failures,
        "source_timings": source_timings,
        "landmark_meta": landmark_meta,
        "matches": matches,
        "summary": summary,
        "latency_quantization_bound_ms": quantization_bound,
        "independent_frame_level_estimate_established": independent_estimate,
        "claim_ceiling": "INDEPENDENT_FRAME_LEVEL_ESTIMATE = ESTABLISHED" if independent_estimate else "INDEPENDENT_FRAME_LEVEL_ESTIMATE = NOT_ESTABLISHED",
    }
