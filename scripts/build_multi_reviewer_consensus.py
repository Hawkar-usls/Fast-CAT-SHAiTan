#!/usr/bin/env python3
"""Build a fail-closed PILOT_001 multi-reviewer consensus report.

Each reviewer contributes three already-frozen artifacts: the attestation, the
bound ingestion analysis, and its independent verifier report. The script does
not create labels or adjudicate disagreements. It preserves non-unanimous state
cells as DISAGREEMENT and only derives events from unanimous frame states.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastcat.review_consensus import build_consensus_report


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--policy",
        default="experiments/pilot_001/multi_reviewer_consensus_protocol.json",
        type=Path,
    )
    parser.add_argument("--analysis", action="append", required=True, type=Path)
    parser.add_argument("--attestation", action="append", required=True, type=Path)
    parser.add_argument("--verifier", action="append", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    if not (
        len(args.analysis) == len(args.attestation) == len(args.verifier)
    ):
        parser.error(
            "--analysis, --attestation and --verifier must be repeated the same number of times"
        )

    policy = _load(args.policy)
    bundles = [
        {
            "analysis": _load(analysis),
            "attestation": _load(attestation),
            "verifier": _load(verifier),
        }
        for analysis, attestation, verifier in zip(
            args.analysis, args.attestation, args.verifier
        )
    ]

    report = build_consensus_report(bundles=bundles, policy=policy)
    report["policy_file"] = str(args.policy)
    report["input_files"] = [
        {
            "analysis": str(analysis),
            "attestation": str(attestation),
            "verifier": str(verifier),
        }
        for analysis, attestation, verifier in zip(
            args.analysis, args.attestation, args.verifier
        )
    ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "scientific_outcome": report.get("scientific_outcome"),
                "failures": report["failures"],
                "reviewer_count": report["reviewer_count"],
                "agreement": report.get("agreement"),
                "consensus_onsets": len(report["derived_consensus_onsets"]),
                "matches": len(report["matches"]),
                "independent_frame_level_estimate_established": report[
                    "independent_frame_level_estimate_established"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
