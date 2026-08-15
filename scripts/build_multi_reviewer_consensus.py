#!/usr/bin/env python3
"""Build a fail-closed PILOT_001 multi-reviewer consensus report.

Each reviewer contributes three already-frozen artifacts: the attestation, the
bound ingestion analysis, and its independent verifier report. Before consensus
is allowed, the complete bundle collection is admitted through the reviewer
collection gate. The script does not create labels or adjudicate disagreements.
It preserves non-unanimous state cells as DISAGREEMENT and only derives events
from unanimous frame states.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastcat.review_consensus import build_consensus_report, canonical_sha256
from fastcat.reviewer_collection import build_reviewer_collection_receipt


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
    parser.add_argument("--analysis", action="append", required=True, type=Path)
    parser.add_argument("--attestation", action="append", required=True, type=Path)
    parser.add_argument("--verifier", action="append", required=True, type=Path)
    parser.add_argument("--collection-out", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    if not (
        len(args.analysis) == len(args.attestation) == len(args.verifier)
    ):
        parser.error(
            "--analysis, --attestation and --verifier must be repeated the same number of times"
        )

    consensus_policy = _load(args.policy)
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

    collection = build_reviewer_collection_receipt(
        bundles=bundles,
        collection_policy=_load(args.collection_policy),
        submission_protocol=_load(args.submission_protocol),
        consensus_policy=consensus_policy,
    )
    if args.collection_out is not None:
        args.collection_out.parent.mkdir(parents=True, exist_ok=True)
        args.collection_out.write_text(
            json.dumps(collection, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if collection["consensus_admission_ready"] is not True:
        report = {
            "schema": "Fast-CAT/PILOT-001/multi-reviewer-consensus/v1.0",
            "status": "FAIL",
            "failures": [
                f"REVIEWER_COLLECTION_NOT_READY:{collection['collection_state']}"
            ]
            + list(collection["failures"]),
            "reviewer_count": len(bundles),
            "reviewer_ids": collection["reviewer_ids"],
            "reviewer_collection_state": collection["collection_state"],
            "reviewer_collection_receipt_sha256": canonical_sha256(collection),
            "consensus_rows": [],
            "derived_consensus_onsets": [],
            "matches": [],
            "multi_reviewer_consensus_established_in_review_scope": False,
            "independent_frame_level_estimate_established": False,
            "claim_ceiling": "Reviewer collection admission did not reach READY_FOR_CONSENSUS. No unanimous state table, action onset, pairing or latency result is admitted.",
        }
    else:
        report = build_consensus_report(bundles=bundles, policy=consensus_policy)
        report["reviewer_collection_state"] = collection["collection_state"]
        report["reviewer_collection_receipt_sha256"] = canonical_sha256(collection)

    report["policy_file"] = str(args.policy)
    report["collection_policy_file"] = str(args.collection_policy)
    report["submission_protocol_file"] = str(args.submission_protocol)
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
                "reviewer_collection_state": report.get(
                    "reviewer_collection_state"
                ),
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
