from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "fastcat.causal_world_bridge.v1"
SOURCE_ROOT = "SOURCE_ROOT"
HYPOTHESIS_ONLY = "HYPOTHESIS_ONLY"


def load_packet(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        packet = json.load(handle)
    if packet.get("schema") != SCHEMA:
        raise ValueError(f"Unsupported schema: {packet.get('schema')!r}")
    worlds = packet.get("worlds")
    if not isinstance(worlds, list) or len(worlds) < 2:
        raise ValueError("At least two source-worlds are required")
    for world in worlds:
        if not world.get("world_id"):
            raise ValueError("Each world requires world_id")
        events = world.get("events")
        if not isinstance(events, list) or not events:
            raise ValueError(f"World {world.get('world_id')} requires non-empty events")
    return packet


def longest_common_prefix(sequences: list[list[str]]) -> list[str]:
    if not sequences:
        return []
    prefix: list[str] = []
    shortest = min(len(sequence) for sequence in sequences)
    for index in range(shortest):
        value = sequences[0][index]
        if all(sequence[index] == value for sequence in sequences[1:]):
            prefix.append(value)
        else:
            break
    return prefix


def pairwise_common_prefix(a: list[str], b: list[str]) -> int:
    count = 0
    for left, right in zip(a, b):
        if left != right:
            break
        count += 1
    return count


def analyze_worlds(packet: dict[str, Any]) -> dict[str, Any]:
    worlds = packet["worlds"]
    sequences = [list(world["events"]) for world in worlds]
    common_prefix = longest_common_prefix(sequences)
    divergence_index = len(common_prefix)

    next_event_by_world: dict[str, str | None] = {}
    for world in worlds:
        events = world["events"]
        next_event_by_world[world["world_id"]] = (
            events[divergence_index] if divergence_index < len(events) else None
        )

    distinct_next = {value for value in next_event_by_world.values()}
    fully_converged = len(distinct_next) == 1 and distinct_next == {None}

    pairwise: list[dict[str, Any]] = []
    for i, left in enumerate(worlds):
        for right in worlds[i + 1 :]:
            pairwise.append(
                {
                    "left": left["world_id"],
                    "right": right["world_id"],
                    "common_prefix_event_count": pairwise_common_prefix(
                        list(left["events"]), list(right["events"])
                    ),
                }
            )

    source_worlds = sorted(
        world["world_id"] for world in worlds if world.get("status") == SOURCE_ROOT
    )
    hypothesis_worlds = sorted(
        world["world_id"] for world in worlds if world.get("status") == HYPOTHESIS_ONLY
    )

    return {
        "schema": "fastcat.causal_world_bridge.result.v1",
        "case_id": packet.get("case_id"),
        "common_prefix": common_prefix,
        "first_divergence_index": None if fully_converged else divergence_index,
        "first_divergence_after": common_prefix[-1] if common_prefix else None,
        "next_event_by_world": next_event_by_world,
        "pairwise_common_prefix": pairwise,
        "source_worlds": source_worlds,
        "hypothesis_worlds": hypothesis_worlds,
        "status": "CONVERGED" if fully_converged else "DISAGREEMENT_PRESERVED",
        "winner": None,
        "historical_claim": "NOT_MADE",
        "cat_rule": (
            "The CAT crosses source-worlds, identifies the first divergence, "
            "preserves disagreement, and never invents a bridge or a winner."
        ),
        "scientific_boundary": (
            "Cross-domain methodology demonstration only. This module does not modify "
            "Fast-CAT feline biological claims and does not treat lore as empirical evidence."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find the first divergence among ordered source-world event sequences."
    )
    parser.add_argument("packet", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    result = analyze_worlds(load_packet(args.packet))
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
