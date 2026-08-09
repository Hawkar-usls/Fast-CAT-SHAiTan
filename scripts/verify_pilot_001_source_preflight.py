#!/usr/bin/env python3
"""Independent source verifier for PILOT_001; intentionally imports no analysis code."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rate(value: str) -> float:
    try:
        return float(Fraction(value))
    except Exception:
        return 0.0


def probe(path: Path) -> dict[str, Any]:
    cp = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], check=True, capture_output=True, text=True)
    return json.loads(cp.stdout)


def video_timing(data: dict[str, Any]) -> dict[str, Any]:
    stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if stream is None:
        raise ValueError("video stream missing")
    fps = rate(str(stream.get("avg_frame_rate", "0/0"))) or rate(str(stream.get("r_frame_rate", "0/0")))
    tb = rate(str(stream.get("time_base", "0/0")))
    if fps <= 0 or tb <= 0:
        raise ValueError("fps/time_base missing")
    duration = stream.get("duration") or data.get("format", {}).get("duration")
    return {
        "width": int(stream.get("width", 0)),
        "height": int(stream.get("height", 0)),
        "fps": fps,
        "time_base": str(stream.get("time_base")),
        "duration_s": float(duration) if duration is not None else None,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--protocol", default="experiments/pilot_001/protocol.json")
    p.add_argument("--manifest", default="data/open_video_sources.json")
    p.add_argument("--receipt-dir", default="data/receipts")
    p.add_argument("--raw-dir", default="data/raw")
    p.add_argument("--out", default="artifacts/pilot_001_source_verifier.json")
    args = p.parse_args()

    protocol = json.loads(Path(args.protocol).read_text(encoding="utf-8"))
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    sources = {x["source_id"]: x for x in manifest["sources"]}
    failures, checked = [], []

    if list(protocol["sources"]) != ["commons_hugging_2019", "commons_tomcats_conflict_2020"]:
        failures.append("FROZEN_SOURCE_ORDER_CHANGED")

    for source_id in protocol["sources"]:
        source = sources.get(source_id)
        if source is None:
            failures.append(f"MANIFEST_SOURCE_MISSING:{source_id}")
            continue
        receipt_path = Path(args.receipt_dir) / f"{source_id}.json"
        if not receipt_path.exists():
            failures.append(f"RECEIPT_MISSING:{source_id}")
            continue
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        raw_path = Path(args.raw_dir) / source_id / Path(source["title"]).name
        if not raw_path.exists():
            failures.append(f"RAW_FILE_MISSING:{source_id}")
            continue

        digest = sha256_file(raw_path)
        if digest != receipt.get("raw_media_sha256"):
            failures.append(f"SHA256_RECEIPT_MISMATCH:{source_id}")
        if raw_path.stat().st_size != int(receipt.get("byte_length", -1)):
            failures.append(f"BYTE_LENGTH_MISMATCH:{source_id}")

        timing = video_timing(probe(raw_path))
        if timing["width"] != int(source["width_px"]) or timing["height"] != int(source["height_px"]):
            failures.append(f"DIMENSION_MISMATCH:{source_id}")
        if timing["duration_s"] is not None and abs(timing["duration_s"] - float(source["duration_s"])) > 0.25:
            failures.append(f"DURATION_MISMATCH:{source_id}")
        if timing != video_timing(receipt["ffprobe"]):
            failures.append(f"FFPROBE_REPLAY_MISMATCH:{source_id}")
        checked.append({"source_id": source_id, "sha256": digest, "byte_length": raw_path.stat().st_size, "timing": timing})

    passed = not failures and len(checked) == len(protocol["sources"])
    report = {
        "schema": "Fast-CAT/PILOT-001/independent-source-verifier/v1.0",
        "status": "PASS" if passed else "FAIL",
        "failures": failures,
        "checked": checked,
        "claim_ceiling": "OPEN_VIDEO + RAW_SHA256 + PTS/FPS only; no landmark or latency claim",
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
