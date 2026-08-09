#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastcat.gate001 import canonical_sha256
from fastcat.genesis_corrections import required_historywise_pmax, source_precision_profile


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--source-preflight", default="experiments/pilot_001/source_preflight.json")
    p.add_argument("--protocol", default="experiments/pilot_001/protocol.json")
    p.add_argument("--out", default="artifacts/pilot_001_genesis_corrections.json")
    args = p.parse_args()

    preflight = json.loads(Path(args.source_preflight).read_text(encoding="utf-8"))
    protocol = json.loads(Path(args.protocol).read_text(encoding="utf-8"))
    precision = source_precision_profile(preflight)

    sequential_examples = []
    for trials in (100, 1000, 10000):
        sequential_examples.append({
            "trials": trials,
            "familywise_alpha": 0.05,
            "candidates_per_trial": 1,
            "required_historywise_per_trial_pmax": required_historywise_pmax(
                familywise_alpha=0.05,
                trials=trials,
                candidates_per_trial=1,
            ),
        })

    report = {
        "schema": "Fast-CAT/PILOT-001/genesis-corrections/v1.0",
        "source_preflight_sha256": canonical_sha256(preflight),
        "protocol_sha256": canonical_sha256(protocol),
        "precision": precision,
        "sequential_false_positive_examples": sequential_examples,
        "model_corrections": [
            "PTS is authoritative; nominal frame_count/fps timestamps are diagnostic only when PTS exists.",
            "A frame-localized delta-t point estimate carries at least one nominal-frame acquisition radius; detector/event-localization uncertainty is additional.",
            "Primary actions and source order are frozen before outcome inspection.",
            "No-match windows are preserved rather than discarded.",
            "If an automated detector is scanned adaptively over many windows, a marginal average false-positive rate is insufficient for a sequential familywise claim; a history-wise conditional cap or an anytime-valid alternative is required.",
            "Multiple candidate events per trial multiply the guessing/false-positive budget and cannot be hidden by postselection."
        ],
        "claim_boundary": "These are acquisition/protocol corrections. They improve calibration and false-positive control but do not replace validated 48-landmark and CatFACS-compatible event-onset evidence."
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
