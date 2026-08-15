#!/usr/bin/env python3
"""Compatibility entrypoint for the active PILOT_001 independent verifier.

The pre-v1.2 verifier bound submissions to one expiring GitHub Actions artifact
ZIP digest. No real reviewer submission was received under that admission
scheme. The active protocol is now content-addressed v1.2, so this familiar
entrypoint deliberately executes the v1.2 independent verifier instead of
silently retaining obsolete transport-digest authority.

Historical verifier behavior remains reproducible from earlier git commits.
"""
from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).with_name("verify_independent_action_review_v1_2.py")),
        run_name="__main__",
    )
