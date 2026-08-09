from __future__ import annotations

import math
from typing import Any


def delta_quantization_interval_ms(delta_ms: float, frame_interval_ms: float) -> dict[str, float]:
    """Conservative acquisition interval for two frame-quantized onsets.

    If both onsets are localized only to decoded frames from the same stream,
    the difference can shift by up to one frame interval relative to the PTS
    point estimate. Detector/event-localization uncertainty is additional and
    is intentionally not hidden inside this acquisition term.
    """
    if not math.isfinite(delta_ms) or delta_ms < 0:
        raise ValueError("delta_ms must be finite and non-negative")
    if not math.isfinite(frame_interval_ms) or frame_interval_ms <= 0:
        raise ValueError("frame_interval_ms must be finite and positive")
    return {
        "point_ms": float(delta_ms),
        "acquisition_lower_ms": max(0.0, float(delta_ms) - float(frame_interval_ms)),
        "acquisition_upper_ms": float(delta_ms) + float(frame_interval_ms),
        "acquisition_radius_ms": float(frame_interval_ms),
    }


def sequential_any_false_positive_bound(*, per_trial_pmax: float, trials: int, candidates_per_trial: int = 1) -> float:
    """JANUS-Genesis-style history-wise familywise bound.

    Valid only when per_trial_pmax is a certified conditional false-positive
    probability cap for every admissible pre-trial history. It is NOT valid
    when the number is merely a marginal/average validation error that can
    collapse on selected histories.
    """
    if not (0.0 <= per_trial_pmax <= 1.0):
        raise ValueError("per_trial_pmax must be in [0,1]")
    if trials < 0:
        raise ValueError("trials must be non-negative")
    if candidates_per_trial < 1:
        raise ValueError("candidates_per_trial must be >= 1")
    q = min(1.0, candidates_per_trial * per_trial_pmax)
    if trials == 0 or q == 0.0:
        return 0.0
    if q == 1.0:
        return 1.0
    return -math.expm1(trials * math.log1p(-q))


def required_historywise_pmax(*, familywise_alpha: float, trials: int, candidates_per_trial: int = 1) -> float:
    """Maximum history-wise per-candidate pmax compatible with a target FWER."""
    if not (0.0 < familywise_alpha < 1.0):
        raise ValueError("familywise_alpha must be in (0,1)")
    if trials < 1:
        raise ValueError("trials must be >= 1")
    if candidates_per_trial < 1:
        raise ValueError("candidates_per_trial must be >= 1")
    per_trial_set = 1.0 - math.exp(math.log1p(-familywise_alpha) / trials)
    return min(1.0, per_trial_set / candidates_per_trial)


def source_precision_profile(source_preflight: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for source in source_preflight.get("sources", []):
        h = float(source["nominal_frame_interval_ms"])
        rows.append({
            "source_id": source["source_id"],
            "fps": float(source["fps"]),
            "nominal_frame_interval_ms": h,
            "delta_acquisition_radius_ms": h,
            "note": "event/model localization uncertainty is additional",
        })
    if not rows:
        raise ValueError("source_preflight contains no sources")
    return {
        "sources": rows,
        "coarsest_delta_acquisition_radius_ms": max(x["delta_acquisition_radius_ms"] for x in rows),
        "finest_delta_acquisition_radius_ms": min(x["delta_acquisition_radius_ms"] for x in rows),
    }
