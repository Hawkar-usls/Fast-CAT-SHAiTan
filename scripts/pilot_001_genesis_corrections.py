#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastcat.gate001 import canonical_sha256
from fastcat.genesis_corrections import required_historywise_pmax


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-preflight",
        default="experiments/pilot_001/source_preflight.json",
    )
    parser.add_argument(
        "--protocol",
        default="experiments/pilot_001/protocol.json",
    )
    parser.add_argument(
        "--out",
        default="artifacts/pilot_001_genesis_corrections.json",
    )
    args = parser.parse_args()

    preflight = json.loads(Path(args.source_preflight).read_text(encoding="utf-8"))
    protocol = json.loads(Path(args.protocol).read_text(encoding="utf-8"))

    sequential_examples = []
    for trials in (100, 1000, 10000):
        sequential_examples.append(
            {
                "trials": trials,
                "familywise_alpha": 0.05,
                "candidates_per_trial": 1,
                "required_historywise_per_trial_pmax": required_historywise_pmax(
                    familywise_alpha=0.05,
                    trials=trials,
                    candidates_per_trial=1,
                ),
            }
        )

    report = {
        "schema": "Fast-CAT/PILOT-001/genesis-corrections/v1.2-runtime",
        "source_preflight_sha256": canonical_sha256(preflight),
        "protocol_sha256": canonical_sha256(protocol),
        "timing_precision": {
            "authority": "decoded_frame_pts",
            "header_fps_role": "diagnostic_only",
            "global_nominal_frame_radius_forbidden": True,
            "final_onset_requirement": (
                "each first-visible onset must carry the immediately previous "
                "reviewed action-absent decoded PTS"
            ),
            "final_latency_interval": (
                "for signaller (s_prev,s] and responder (r_prev,r], "
                "report point r-s and acquisition interval [r_prev-s, r-s_prev]"
            ),
            "note": (
                "This runtime artifact intentionally does not derive millisecond "
                "precision from avg_frame_rate/r_frame_rate. Decoded-frame ledgers "
                "are verified in the dedicated frame-ledger gate."
            ),
        },
        "sequential_false_positive_examples": sequential_examples,
        "model_corrections": [
            "Decoded frame PTS is authoritative; stream-header FPS is diagnostic only.",
            "No global nominal-FPS acquisition radius is admitted.",
            "Final event timing requires previous-absent and first-present decoded PTS brackets.",
            "Primary actions and source order are frozen before outcome inspection.",
            "No-match windows are preserved rather than discarded.",
            "A marginal or average detector false-positive rate is insufficient for an adaptive sequential familywise claim; a history-wise conditional cap or an anytime-valid alternative is required.",
            "Multiple candidate events per trial multiply the guessing/false-positive budget and cannot be hidden by postselection.",
        ],
        "claim_boundary": (
            "These are protocol and false-positive-control corrections. They do "
            "not replace validated two-cat identity, 48-landmark accuracy, or "
            "CatFACS-compatible action-onset evidence."
        ),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
