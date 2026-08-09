#!/usr/bin/env python3
"""Independently replay a PILOT_001 decoded-frame ledger.

This verifier intentionally does not import build_frame_ledger.py or fastcat.gate001.
It recomputes source SHA-256, decoded-frame PTS, deterministic sample membership,
RGB24 pixel hashes, and review PNG byte hashes from first principles.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any


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


def probe_stream(video: Path) -> dict[str, Any]:
    raw = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_streams", "-of", "json", str(video),
        ]
    )
    data = json.loads(raw.decode("utf-8"))
    streams = data.get("streams", [])
    if len(streams) != 1:
        raise RuntimeError(f"EXPECTED_ONE_VIDEO_STREAM:{len(streams)}")
    return streams[0]


def probe_frame_pts(video: Path) -> list[dict[str, Any]]:
    raw = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_frames", "-show_entries",
            "frame=best_effort_timestamp_time,pkt_dts_time,key_frame,pict_type",
            "-of", "json", str(video),
        ]
    )
    data = json.loads(raw.decode("utf-8"))
    frames = data.get("frames", [])
    out: list[dict[str, Any]] = []
    last: Decimal | None = None
    for index, frame in enumerate(frames):
        pts = frame.get("best_effort_timestamp_time")
        if pts in (None, ""):
            pts = frame.get("pkt_dts_time")
        if pts in (None, ""):
            raise RuntimeError(f"PTS_MISSING:{index}")
        d = Decimal(str(pts))
        if last is not None and d <= last:
            raise RuntimeError(f"PTS_NOT_STRICT:{index}:{d}<={last}")
        last = d
        out.append({
            "frame_index": index,
            "pts_s": str(pts),
            "key_frame": int(frame.get("key_frame", 0)),
            "pict_type": str(frame.get("pict_type", "")),
        })
    if not out:
        raise RuntimeError("NO_FRAMES")
    return out


def expected_indices(frame_count: int, step: int) -> list[int]:
    values = list(range(0, frame_count, step))
    if values[-1] != frame_count - 1:
        values.append(frame_count - 1)
    return values


def rgb24_hash(video: Path, index: int, width: int, height: int) -> tuple[str, int]:
    raw = subprocess.check_output(
        [
            "ffmpeg", "-v", "error", "-i", str(video),
            "-vf", f"select=eq(n\\,{index})", "-frames:v", "1",
            "-an", "-sn", "-dn", "-pix_fmt", "rgb24",
            "-f", "rawvideo", "pipe:1",
        ]
    )
    expected_len = width * height * 3
    if len(raw) != expected_len:
        raise RuntimeError(f"RGB_LENGTH:{index}:{len(raw)}!={expected_len}")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def verify(args: argparse.Namespace) -> dict[str, Any]:
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    failures: list[str] = []

    if ledger.get("schema") != "Fast-CAT/PILOT-001/decoded-frame-ledger/v1.0":
        failures.append("SCHEMA_MISMATCH")
    if ledger.get("source_id") != args.source_id:
        failures.append("SOURCE_ID_MISMATCH")

    raw_sha = sha256_file(args.video)
    if raw_sha != ledger.get("source_media_sha256"):
        failures.append("SOURCE_MEDIA_SHA256_MISMATCH")

    stream = probe_stream(args.video)
    width = int(stream.get("width", 0))
    height = int(stream.get("height", 0))
    expected_stream = {
        "codec_name": stream.get("codec_name"),
        "width": width,
        "height": height,
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "r_frame_rate": stream.get("r_frame_rate"),
        "time_base": stream.get("time_base"),
    }
    if expected_stream != ledger.get("stream"):
        failures.append("STREAM_DESCRIPTOR_MISMATCH")

    frame_pts = probe_frame_pts(args.video)
    if len(frame_pts) != int(ledger.get("frame_count", -1)):
        failures.append("FRAME_COUNT_MISMATCH")
    pts_digest = canonical_sha256(frame_pts)
    if pts_digest != ledger.get("frame_pts_sha256"):
        failures.append("FRAME_PTS_SHA256_MISMATCH")
    if frame_pts != ledger.get("frame_pts"):
        failures.append("FRAME_PTS_CONTENT_MISMATCH")

    selection = ledger.get("selection", {})
    step = int(selection.get("step_frames", 0))
    if step <= 0:
        failures.append("STEP_FRAMES_INVALID")
        expected = []
    else:
        expected = expected_indices(len(frame_pts), step)
    selected = selection.get("selected", [])
    selected_indices = [int(x.get("frame_index", -1)) for x in selected]
    if selected_indices != expected:
        failures.append("SELECTED_INDEX_SET_MISMATCH")
    if int(selection.get("selected_count", -1)) != len(selected):
        failures.append("SELECTED_COUNT_MISMATCH")

    pixel_checks = 0
    png_checks = 0
    for item in selected:
        index = int(item["frame_index"])
        if index < 0 or index >= len(frame_pts):
            failures.append(f"FRAME_INDEX_OUT_OF_RANGE:{index}")
            continue
        if str(item.get("pts_s")) != frame_pts[index]["pts_s"]:
            failures.append(f"SELECTED_PTS_MISMATCH:{index}")

        digest, byte_length = rgb24_hash(args.video, index, width, height)
        pixel_checks += 1
        if digest != item.get("rgb24_sha256"):
            failures.append(f"RGB24_SHA256_MISMATCH:{index}")
        if byte_length != int(item.get("rgb24_byte_length", -1)):
            failures.append(f"RGB24_BYTE_LENGTH_MISMATCH:{index}")

        png_path = args.frame_dir / str(item.get("png_filename", ""))
        if not png_path.is_file():
            failures.append(f"PNG_MISSING:{index}")
        else:
            png_checks += 1
            if sha256_file(png_path) != item.get("png_sha256"):
                failures.append(f"PNG_SHA256_MISMATCH:{index}")

    payload = {
        "source_id": ledger.get("source_id"),
        "source_media_sha256": ledger.get("source_media_sha256"),
        "stream": ledger.get("stream"),
        "frame_count": ledger.get("frame_count"),
        "frame_pts_sha256": ledger.get("frame_pts_sha256"),
        "selection": ledger.get("selection"),
    }
    payload_digest = canonical_sha256(payload)
    if payload_digest != ledger.get("ledger_payload_sha256"):
        failures.append("LEDGER_PAYLOAD_SHA256_MISMATCH")

    report = {
        "schema": "Fast-CAT/PILOT-001/decoded-frame-ledger-verifier/v1.0",
        "source_id": args.source_id,
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "source_media_sha256": raw_sha,
        "frame_count_recomputed": len(frame_pts),
        "frame_pts_sha256_recomputed": pts_digest,
        "ledger_payload_sha256_recomputed": payload_digest,
        "selected_frames_replayed": pixel_checks,
        "review_pngs_rehashed": png_checks,
        "claim_ceiling": "Independent replay of source bytes, decoded PTS, deterministic sample membership and RGB24 pixel identity only.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return report


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--source-id", required=True)
    p.add_argument("--video", required=True, type=Path)
    p.add_argument("--ledger", required=True, type=Path)
    p.add_argument("--frame-dir", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    return p.parse_args()


if __name__ == "__main__":
    result = verify(parse_args())
    raise SystemExit(0 if result["status"] == "PASS" else 1)
