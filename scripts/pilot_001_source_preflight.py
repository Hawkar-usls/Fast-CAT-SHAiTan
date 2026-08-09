#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastcat.gate001 import canonical_sha256, timing_descriptor, validate_source_receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", default="experiments/pilot_001/protocol.json")
    parser.add_argument("--manifest", default="data/open_video_sources.json")
    parser.add_argument("--receipt-dir", default="data/receipts")
    parser.add_argument("--out", default="artifacts/pilot_001_source_preflight.json")
    args = parser.parse_args()

    protocol = json.loads(Path(args.protocol).read_text(encoding="utf-8"))
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    sources = {x["source_id"]: x for x in manifest["sources"]}
    failures, rows = [], []

    for source_id in protocol["sources"]:
        receipt_path = Path(args.receipt_dir) / f"{source_id}.json"
        if not receipt_path.exists():
            failures.append(f"SOURCE_RECEIPT_MISSING:{source_id}")
            continue
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        source = sources.get(source_id)
        if source is None:
            failures.append(f"MANIFEST_SOURCE_MISSING:{source_id}")
            continue
        source_failures = validate_source_receipt(receipt, source)
        failures.extend(f"{source_id}:{x}" for x in source_failures)
        timing = timing_descriptor(receipt["ffprobe"]) if not source_failures else None
        rows.append({
            "source_id": source_id,
            "source_page": source["source_page"],
            "license": source["license"],
            "raw_media_sha256": receipt.get("raw_media_sha256"),
            "byte_length": receipt.get("byte_length"),
            "timing": timing,
            "source_receipt_sha256": canonical_sha256(receipt),
        })

    passed = not failures and len(rows) == len(protocol["sources"])
    report = {
        "schema": "Fast-CAT/PILOT-001/source-preflight/v1.0",
        "status": "PASS" if passed else "FAIL",
        "failures": failures,
        "sources": rows,
        "protocol_sha256": canonical_sha256(protocol),
        "manifest_sha256": canonical_sha256(manifest),
        "established_scope": ["OPEN_VIDEO", "RAW_SHA256", "PTS_FPS_METADATA"] if passed else [],
        "not_established": ["48_LANDMARKS", "FACIAL_ACTION_ONSET", "DELTA_T", "INDEPENDENT_FRAME_LEVEL_ESTIMATE"],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
