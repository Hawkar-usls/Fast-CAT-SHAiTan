from __future__ import annotations

import math


def decoded_pts_latency_interval_ms(
    *,
    signaller_previous_absent_pts_s: float,
    signaller_onset_pts_s: float,
    responder_previous_absent_pts_s: float,
    responder_onset_pts_s: float,
) -> dict[str, float]:
    """Acquisition interval from actual decoded-PTS onset brackets.

    An admitted first-visible onset is bracketed by the immediately previous
    reviewed decoded frame where the action is absent and the first reviewed
    decoded frame where it is present. Header FPS is deliberately absent from
    this calculation.
    """
    sp = float(signaller_previous_absent_pts_s)
    s = float(signaller_onset_pts_s)
    rp = float(responder_previous_absent_pts_s)
    r = float(responder_onset_pts_s)
    if not all(math.isfinite(x) for x in (sp, s, rp, r)):
        raise ValueError("PTS values must be finite")
    if not (0.0 <= sp < s <= r and 0.0 <= rp < r):
        raise ValueError("invalid decoded-PTS onset brackets")

    point = (r - s) * 1000.0
    lower = (rp - s) * 1000.0
    upper = (r - sp) * 1000.0
    return {
        "point_ms": point,
        "acquisition_lower_ms": lower,
        "acquisition_upper_ms": upper,
        "signaller_bracket_ms": (s - sp) * 1000.0,
        "responder_bracket_ms": (r - rp) * 1000.0,
        "acquisition_interval_width_ms": upper - lower,
    }


def sequential_any_false_positive_bound(
    *,
    per_trial_pmax: float,
    trials: int,
    candidates_per_trial: int = 1,
) -> float:
    """JANUS-Genesis-style history-wise familywise bound.

    Valid only when ``per_trial_pmax`` is a certified conditional false-positive
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


def required_historywise_pmax(
    *,
    familywise_alpha: float,
    trials: int,
    candidates_per_trial: int = 1,
) -> float:
    """Maximum history-wise per-candidate pmax compatible with a target FWER."""
    if not (0.0 < familywise_alpha < 1.0):
        raise ValueError("familywise_alpha must be in (0,1)")
    if trials < 1:
        raise ValueError("trials must be >= 1")
    if candidates_per_trial < 1:
        raise ValueError("candidates_per_trial must be >= 1")
    per_trial_set = 1.0 - math.exp(math.log1p(-familywise_alpha) / trials)
    return min(1.0, per_trial_set / candidates_per_trial)
