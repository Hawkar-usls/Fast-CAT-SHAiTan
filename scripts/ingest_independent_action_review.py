#!/usr/bin/env python3
"""Ingest a completed independent PILOT_001 blinded action review.

This command never creates review labels. It first proves that the submission is
bound to the exact frozen model-blinded package, then validates an externally
completed CSV + reviewer attestation, derives first-visible onsets
deterministically, and pairs same-action cross-subject events under the frozen
protocol.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastcat.bound_review_ingestion import build_bound_submission_report
from fastcat.review_ingestion import read_review_csv, sha256_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        default="experiments/pilot_001/independent_review_submission_protocol.json",
        type=Path,
    )
    parser.add_argument("--frame-manifest", required=True, type=Path)
    parser.add_argument("--review-form", required=True, type=Path)
    parser.add_argument("--attestation", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    frame_manifest = json.loads(args.frame_manifest.read_text(encoding="utf-8"))
    attestation = json.loads(args.attestation.read_text(encoding="utf-8"))
    headers, rows = read_review_csv(args.review_form)
    form_sha = sha256_file(args.review_form)
    frame_manifest_sha = sha256_file(args.frame_manifest)

    report = build_bound_submission_report(
        protocol=protocol,
        frame_manifest=frame_manifest,
        frame_manifest_file_sha256=frame_manifest_sha,
        headers=headers,
        review_rows=rows,
        attestation=attestation,
        completed_review_form_sha256=form_sha,
    )
    report["protocol_sha256"] = sha256_file(args.protocol)
    report["frame_manifest_file_sha256"] = frame_manifest_sha
    report["attestation_file_sha256"] = sha256_file(args.attestation)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "scientific_outcome": report["scientific_outcome"],
                "failures": report["failures"],
                "exact_frozen_package_binding_established": report.get(
                    "exact_frozen_package_binding_established", False
                ),
                "derived_onsets": len(report["derived_onsets"]),
                "matches": report["summary"]["n_matches"],
                "completed_review_form_sha256": report[
                    "completed_review_form_sha256"
                ],
                "derived_onsets_sha256": report["derived_onsets_sha256"],
                "matches_sha256": report["matches_sha256"],
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
