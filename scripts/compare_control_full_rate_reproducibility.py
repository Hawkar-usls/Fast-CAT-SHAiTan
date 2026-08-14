#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastcat.numerical_reproducibility import compare_triage_reports


def load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument(
        "--protocol",
        default="experiments/pilot_001/control_full_rate_numerical_reproducibility.json",
        type=Path,
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    report = compare_triage_reports(
        baseline=load(args.baseline),
        candidate=load(args.candidate),
        protocol=load(args.protocol),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "VALIDATED_WITHIN_FROZEN_NUMERICAL_TOLERANCE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
