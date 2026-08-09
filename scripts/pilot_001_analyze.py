#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fastcat.gate001 import canonical_sha256, gate_report


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return rows


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--protocol", default="experiments/pilot_001/protocol.json")
    p.add_argument("--manifest", default="data/open_video_sources.json")
    p.add_argument("--receipt-dir", default="data/receipts")
    p.add_argument("--landmarks", required=True, help="JSONL: one 48-landmark row per cat/frame")
    p.add_argument("--events", required=True, help="JSONL: preregistered/reviewed facial-action onsets")
    p.add_argument("--out", default="artifacts/pilot_001_analysis.json")
    args = p.parse_args()

    protocol = json.loads(Path(args.protocol).read_text(encoding="utf-8"))
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    manifest_sources = {x["source_id"]: x for x in manifest["sources"]}
    receipts = []
    for source_id in protocol["sources"]:
        path = Path(args.receipt_dir) / f"{source_id}.json"
        if not path.exists():
            raise SystemExit(f"missing source receipt: {path}")
        receipts.append(json.loads(path.read_text(encoding="utf-8")))

    landmarks, events = read_jsonl(Path(args.landmarks)), read_jsonl(Path(args.events))
    report = gate_report(source_receipts=receipts, manifest_sources=manifest_sources, protocol=protocol, landmark_rows=landmarks, event_rows=events)
    report["inputs"] = {
        "protocol_sha256": canonical_sha256(protocol),
        "manifest_sha256": canonical_sha256(manifest),
        "landmarks_sha256": canonical_sha256(landmarks),
        "events_sha256": canonical_sha256(events),
        "source_receipts_sha256": canonical_sha256(receipts),
    }
    report["analysis_payload_sha256"] = canonical_sha256({
        "matches": report["matches"],
        "summary": report["summary"],
        "stages": report["stages"],
        "latency_quantization_bound_ms": report["latency_quantization_bound_ms"],
    })
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["independent_frame_level_estimate_established"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
