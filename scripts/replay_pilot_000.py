#!/usr/bin/env python3
"""Deterministically replay Fast-CAT-SHAiTan PILOT_000.

This is a reproducibility/sanity-check program over the example event sequence
published by Martvel et al. (2024). It does not analyze raw video and does not
establish a biological reaction-time distribution.
"""

from __future__ import annotations

import hashlib
import json
import statistics
from typing import Any

WINDOW_S = 1.0
EXPECTED_EVENTS_SHA256 = "7d4f5284c53d16438b48344fa57cdbd72927cf35b429f45f46af64f2584ef2c2"
EXPECTED_ANALYSIS_SHA256 = "a36f7321c1c3f15adaffb5c8195058c0ff02f12a270e0a8628b69eb8bfb8df28"

EVENTS: list[dict[str, Any]] = [
    {"actor": "signaller", "action": "AU25", "t_s": 0.0},
    {"actor": "signaller", "action": "AU26", "t_s": 0.3},
    {"actor": "responder", "action": "AU25", "t_s": 0.3},
    {"actor": "signaller", "action": "EAD102", "t_s": 0.45},
    {"actor": "responder", "action": "AU26", "t_s": 0.45},
    {"actor": "signaller", "action": "EAD104", "t_s": 1.0},
    {"actor": "responder", "action": "AU47", "t_s": 1.0},
    {"actor": "responder", "action": "EAD104", "t_s": 1.15},
    {"actor": "responder", "action": "EAD105", "t_s": 2.0},
]


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def replay(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    matches: list[dict[str, Any]] = []

    for index, event in enumerate(events):
        if event["actor"] != "signaller":
            continue

        for candidate in events[index + 1 :]:
            if candidate["actor"] != "responder":
                continue
            if candidate["action"] != event["action"]:
                continue

            dt_s = float(candidate["t_s"]) - float(event["t_s"])
            if 0.0 <= dt_s <= WINDOW_S:
                matches.append(
                    {
                        "action": event["action"],
                        "signaller_t_s": event["t_s"],
                        "responder_t_s": candidate["t_s"],
                        "latency_ms": round(dt_s * 1000.0),
                    }
                )
                break

    latencies = [int(match["latency_ms"]) for match in matches]
    if not latencies:
        raise RuntimeError("PILOT_000 produced no matching events")

    summary = {
        "n_matches": len(latencies),
        "latencies_ms": latencies,
        "mean_ms": float(statistics.mean(latencies)),
        "median_ms": int(statistics.median(latencies)),
        "min_ms": min(latencies),
        "max_ms": max(latencies),
    }
    return matches, summary


def main() -> int:
    matches, summary = replay(EVENTS)
    analysis_payload = {"events": EVENTS, "matches": matches, "summary": summary}

    events_digest = sha256(EVENTS)
    analysis_digest = sha256(analysis_payload)

    assert events_digest == EXPECTED_EVENTS_SHA256, (events_digest, EXPECTED_EVENTS_SHA256)
    assert analysis_digest == EXPECTED_ANALYSIS_SHA256, (analysis_digest, EXPECTED_ANALYSIS_SHA256)
    assert summary == {
        "n_matches": 3,
        "latencies_ms": [300, 150, 150],
        "mean_ms": 200.0,
        "median_ms": 150,
        "min_ms": 150,
        "max_ms": 300,
    }

    output = {
        "experiment_id": "PILOT_000",
        "status": "PASS",
        "window_ms": int(WINDOW_S * 1000),
        "matches": matches,
        "summary": summary,
        "events_sha256": events_digest,
        "analysis_payload_sha256": analysis_digest,
        "claim_ceiling": "published-example replay only; no independent raw-video latency estimate",
    }
    print(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
