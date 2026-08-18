#!/usr/bin/env python3
"""Fast-CAT-style software replay for the CG 53469 handoff.

This reuses Fast-CAT's admission discipline only. It is NOT Egyptological
expert review and NOT independent external evidence. Two separately coded rule
paths must agree on what the existing handoff admits:
  1) catalogue object-class identity;
  2) human funerary context;
  3) unique original Osiris-relic identity.

Any missing external custody/conservation/imaging discriminator leaves the
third claim NOT_ADMITTED. Negative/inconclusive is a valid terminal state.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / ".janus" / "CAT_GUBOSVET_OSIRIS_HANDOFF_2026-08-18.json"

PASS = "PASS"
OPEN = "OPEN"
NOT_ADMITTED = "NOT_ADMITTED"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verifier_a(doc: dict) -> dict[str, str]:
    piece = doc["recognized_piece"]
    path = doc["cat_gubosvet_task"]["admission_path"]

    catalogue = PASS if (
        piece.get("catalogue_object") == "CG 53469"
        and piece.get("catalogue_label") == "Enveloppe de phallus"
        and piece.get("catalogue_class_status") == "IDENTIFIED_IN_ARCHIVED_PROJECT_RECEIPTS"
    ) else OPEN

    funerary = PASS if (
        "MENDES_1902_FUNERARY_CONTEXT = PASS" in path
        and "HISTORICAL_PLATE = PASS" in path
    ) else OPEN

    required_open = {
        "CURRENT_CUSTODY_RECORD = OPEN",
        "CURRENT_MULTI_ANGLE_PHOTOGRAPHY = OPEN",
        "CONSERVATION_HISTORY = OPEN",
        "NONDESTRUCTIVE_INTERNAL_IMAGING_IF_APPROPRIATE = OPEN",
    }
    relic = NOT_ADMITTED if (
        piece.get("mythic_owner_identity") == "NOT_ESTABLISHED"
        and required_open.issubset(set(path))
        and "MATCHED_HUMAN_FUNERARY_CONTROLS = REQUIRED" in path
    ) else OPEN

    return {
        "CATALOGUE_OBJECT_CLASS": catalogue,
        "HUMAN_FUNERARY_CONTEXT": funerary,
        "UNIQUE_ORIGINAL_OSIRIS_RELIC_IDENTITY": relic,
    }


def verifier_b(doc: dict) -> dict[str, str]:
    piece = doc.get("recognized_piece", {})
    task = doc.get("cat_gubosvet_task", {})
    path_text = "\n".join(task.get("admission_path", []))
    firewall = set(doc.get("firewall", []))

    catalogue_tokens = [
        piece.get("catalogue_object") == "CG 53469",
        piece.get("material") == "gold",
        piece.get("historical_plate") == "LXXXVII",
        piece.get("plate_visible_label") == "53.469",
    ]
    catalogue = PASS if all(catalogue_tokens) else OPEN

    funerary_tokens = (
        "MENDES_1902_FUNERARY_CONTEXT = PASS" in path_text,
        piece.get("find_date") == "February 1902",
        "CATALOGUE_IDENTITY != MYTHIC_OWNER_IDENTITY" in firewall,
    )
    funerary = PASS if all(funerary_tokens) else OPEN

    independent_discriminators_missing = all(token in path_text for token in (
        "CURRENT_CUSTODY_RECORD = OPEN",
        "CURRENT_MULTI_ANGLE_PHOTOGRAPHY = OPEN",
        "CONSERVATION_HISTORY = OPEN",
    ))
    explicit_nonpromotion = (
        "CG53469_GOLD_PHALLUS_SHEATH != ORIGINAL_OSIRIS_PHALLUS" in firewall
        and "UNIQUE_ORIGINAL_OSIRIS_RELIC_IDENTITY = NOT_ESTABLISHED" in path_text
    )
    relic = NOT_ADMITTED if independent_discriminators_missing and explicit_nonpromotion else OPEN

    return {
        "CATALOGUE_OBJECT_CLASS": catalogue,
        "HUMAN_FUNERARY_CONTEXT": funerary,
        "UNIQUE_ORIGINAL_OSIRIS_RELIC_IDENTITY": relic,
    }


def main() -> None:
    doc = json.loads(HANDOFF.read_text(encoding="utf-8"))
    a = verifier_a(doc)
    b = verifier_b(doc)
    assert a == b, {"verifier_a": a, "verifier_b": b}

    expected = {
        "CATALOGUE_OBJECT_CLASS": PASS,
        "HUMAN_FUNERARY_CONTEXT": PASS,
        "UNIQUE_ORIGINAL_OSIRIS_RELIC_IDENTITY": NOT_ADMITTED,
    }
    assert a == expected, {"expected": expected, "observed": a}

    result = {
        "run_class": "SOFTWARE_REPLAY_ONLY_NOT_EXTERNAL_REVIEW",
        "handoff_sha256": sha256(HANDOFF),
        "verifier_a": a,
        "verifier_b": b,
        "exact_unanimity": True,
        "admitted_claims": [
            "CG53469_IS_CATALOGUED_AS_GOLD_PHALLUS_SHEATH_IN_PROJECT_RECEIPTS",
            "CG53469_IS_BOUND_TO_MENDES_1902_HUMAN_FUNERARY_CONTEXT_IN_PROJECT_RECEIPTS",
        ],
        "rejected_promotion": "CG53469_IS_UNIQUE_ORIGINAL_OSIRIS_RELIC",
        "next_gate": doc["cat_gubosvet_task"]["next_best_gate"],
        "claim_ceiling": "CATALOGUE_AND_FUNERARY_RECOGNITION_ONLY",
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    print("CAT_GUBOSVET_EXACT_UNANIMITY_SOFTWARE_REPLAY = PASS")
    print("ORIGINAL_OSIRIS_RELIC_IDENTITY = NOT_ADMITTED")


if __name__ == "__main__":
    main()
