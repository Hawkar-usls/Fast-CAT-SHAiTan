#!/usr/bin/env python3
"""Build a fail-closed PILOT_001 reviewer collection readiness receipt.

Zero or one valid reviewer bundle is an expected waiting state, not a software
failure. Two or more admissible distinct bundles may enter the already-frozen
multi-reviewer consensus gate. Invalid or tampered bundles fail closed.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastcat.reviewer_collection import build_reviewer_collection_receipt


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--collection-policy",
        default="experiments/pilot_001/reviewer_collection_protocol.json",
        type=Path,
    )
    parser.add_argument(
        "--submission-protocol",
        default="experiments/pilot_001/independent_review_submission_protocol.json",
        type=Path,
    )
    parser.add_argument(
        "--consensus-policy",
        default="experiments/pilot_001/multi_reviewer_consensus_protocol.json",
        type=Path,
    )
    parser.add_argument("--analysis", action="append", default=[], type=Path)
    parser.add_argument("--attestation", action="append", default=[], type=Path)
    parser.add_argument("--verifier", action="append", default=[], type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    if not (
        len(args.analysis) == len(args.attestation) == len(args.verifier)
    ):
        parser.error(
            "--analysis, --attestation and --verifier must be repeated the same number of times"
        )

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
    report = build_reviewer_collection_receipt(
        bundles=bundles,
        collection_policy=_load(args.collection_policy),
        submission_protocol=_load(args.submission_protocol),
        consensus_policy=_load(args.consensus_policy),
    )
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
    report["collection_policy_file"] = str(args.collection_policy)
    report["submission_protocol_file"] = str(args.submission_protocol)
    report["consensus_policy_file"] = str(args.consensus_policy)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "collection_state": report["collection_state"],
                "failures": report["failures"],
                "submitted_bundle_count": report["submitted_bundle_count"],
                "admissible_bundle_count": report["admissible_bundle_count"],
                "consensus_admission_ready": report["consensus_admission_ready"],
                "human_independence_proven_by_software": report[
                    "human_independence_proven_by_software"
                ],
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
