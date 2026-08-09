#!/usr/bin/env python3
"""Build the PILOT_001 model-blinded EAD103/EAD104 review package.

The package intentionally contains raw decoded review frames, decoded PTS and an
empty annotation form. It excludes landmarks, model scores, rankings and action
predictions. This script does not create scientific labels.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

EXPECTED_SOURCE_ID = "commons_hugging_2019"
EXPECTED_RAW_SHA256 = "1ac95b351424d63d944969e19949a925e502fbb380153aa404f99390c9845e2e"
EXPECTED_FRAME_COUNT = 50
EXPECTED_PTS_SHA256 = "98532adfb0c29815d780116b557802d2b45a81ae47a0cb6a8e569973684e31ee"
SUBJECTS = ("subject_A", "subject_B")
LABEL_COLUMNS = (
    "left_ear_EAD103",
    "right_ear_EAD103",
    "left_ear_EAD104",
    "right_ear_EAD104",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def instructions_text() -> str:
    return """# PILOT_001 blinded EAD103/EAD104 frame review

## Independence boundary

This package is for a reviewer who has **not** seen Fast-CAT landmark overlays,
motion scores, motion rankings, predicted actions, or model-generated onset
candidates before freezing their labels.

The current ChatGPT/model-assisted development session is not an eligible
independent reviewer because it has already inspected model-derived evidence.

## Subjects

- `subject_A`: tabby/brown cat, left/foreground in this frozen short source.
- `subject_B`: black cat, right/background in this frozen short source.

Confirm identity independently on every row. If identity is not confidently
traceable in a frame, use `no` or `uncertain` in `identity_confirmed` rather than
assuming the subject label from prior frames.

## Labels

For each subject, frame and ear, assign exactly one state:

- `ABSENT`
- `PRESENT`
- `UNCERTAIN`
- `NOT_VISIBLE`

Review the frames in chronological order. Do not skip low-motion or apparently
uninteresting frames.

### Appearance guidance

`EAD103` is reviewed as an ear-flattener appearance: the pinna is pulled
caudally and flattened toward the head. `EAD104` is reviewed as an ear-rotator
appearance: the pinna rotates caudally/laterally. These appearance notes are a
review aid only; final feline coding should not be presented as certified
CatFACS coding unless the reviewer has appropriate CatFACS competence or the
automated action detector has been separately validated.

Global head rotation, exposure changes, blur or an ambiguous pinna contour do
not establish an ear action. Use `UNCERTAIN` or `NOT_VISIBLE` when the relevant
ear cannot be judged.

## Timing rule

Do not manually type timestamps. The form already binds each frame to decoded
PTS. After labels are frozen, an onset may be derived only when an immediately
previous decoded frame is `ABSENT` and the next decoded frame is `PRESENT` for
the same subject/action/laterality. `UNCERTAIN` and `NOT_VISIBLE` cannot bridge
an onset.

## Freeze rule

Complete every row, save the CSV without adding model fields, then compute and
record its SHA-256 before any Fast-CAT landmark/motion ranking is revealed.
That frozen label file can then enter the separate onset/matching verifier.
"""


def build(args: argparse.Namespace) -> dict[str, Any]:
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    ledger = json.loads(args.frame_ledger.read_text(encoding="utf-8"))

    if protocol.get("schema") != "Fast-CAT/PILOT-001/blinded-review-package-protocol/v1.0":
        raise RuntimeError("PROTOCOL_SCHEMA_MISMATCH")
    if ledger.get("source_id") != EXPECTED_SOURCE_ID:
        raise RuntimeError("SOURCE_ID_MISMATCH")
    if ledger.get("source_media_sha256") != EXPECTED_RAW_SHA256:
        raise RuntimeError("RAW_SHA256_MISMATCH")
    if int(ledger.get("frame_count", -1)) != EXPECTED_FRAME_COUNT:
        raise RuntimeError("FRAME_COUNT_MISMATCH")
    if ledger.get("frame_pts_sha256") != EXPECTED_PTS_SHA256:
        raise RuntimeError("FRAME_PTS_SHA256_MISMATCH")

    selected = ledger.get("selection", {}).get("selected", [])
    if len(selected) != EXPECTED_FRAME_COUNT:
        raise RuntimeError(f"FULL_FRAME_SELECTION_REQUIRED:{len(selected)}")
    selected_indices = [int(x["frame_index"]) for x in selected]
    if selected_indices != list(range(EXPECTED_FRAME_COUNT)):
        raise RuntimeError("SELECTED_FRAME_SEQUENCE_MISMATCH")

    out = args.out_dir.resolve()
    frame_out = out / "frames"
    frame_out.mkdir(parents=True, exist_ok=True)

    frame_manifest: list[dict[str, Any]] = []
    for item in selected:
        frame_index = int(item["frame_index"])
        filename = str(item["png_filename"])
        src = args.frame_dir / filename
        if not src.is_file():
            raise RuntimeError(f"FRAME_FILE_MISSING:{frame_index}:{filename}")
        if sha256_file(src) != str(item["png_sha256"]):
            raise RuntimeError(f"FRAME_PNG_SHA256_MISMATCH:{frame_index}")
        dst = frame_out / filename
        shutil.copyfile(src, dst)
        if sha256_file(dst) != str(item["png_sha256"]):
            raise RuntimeError(f"COPIED_FRAME_SHA256_MISMATCH:{frame_index}")
        frame_manifest.append(
            {
                "frame_index": frame_index,
                "pts_s": str(item["pts_s"]),
                "filename": filename,
                "png_sha256": str(item["png_sha256"]),
                "rgb24_sha256": str(item["rgb24_sha256"]),
            }
        )

    manifest_payload = {
        "schema": "Fast-CAT/PILOT-001/blinded-review-frame-manifest/v1.0",
        "source_id": EXPECTED_SOURCE_ID,
        "raw_media_sha256": EXPECTED_RAW_SHA256,
        "frame_count": EXPECTED_FRAME_COUNT,
        "frame_pts_sha256": EXPECTED_PTS_SHA256,
        "frames": frame_manifest,
        "contains_model_derived_fields": False,
        "claim_ceiling": "Raw decoded review-frame identity and PTS only; no action labels or model evidence.",
    }
    frame_manifest_path = out / "frame_manifest.json"
    frame_manifest_path.write_text(
        json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    form_path = out / "review_form.csv"
    fieldnames = [
        "source_id",
        "frame_index",
        "pts_s",
        "subject_id",
        "identity_confirmed",
        *LABEL_COLUMNS,
        "review_notes",
    ]
    with form_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for frame in frame_manifest:
            for subject in SUBJECTS:
                row: dict[str, Any] = {
                    "source_id": EXPECTED_SOURCE_ID,
                    "frame_index": frame["frame_index"],
                    "pts_s": frame["pts_s"],
                    "subject_id": subject,
                    "identity_confirmed": "",
                    "review_notes": "",
                }
                for column in LABEL_COLUMNS:
                    row[column] = ""
                writer.writerow(row)

    instructions_path = out / "REVIEW_INSTRUCTIONS.md"
    instructions_path.write_text(instructions_text(), encoding="utf-8")

    package_files = [
        frame_manifest_path,
        form_path,
        instructions_path,
        *sorted(frame_out.glob("*.png")),
    ]
    package_manifest = {
        "schema": "Fast-CAT/PILOT-001/blinded-review-package-manifest/v1.0",
        "source_id": EXPECTED_SOURCE_ID,
        "protocol_sha256": sha256_file(args.protocol),
        "frame_ledger_sha256": sha256_file(args.frame_ledger),
        "files": [
            {
                "path": str(path.relative_to(out)).replace("\\", "/"),
                "byte_length": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in package_files
        ],
        "expected_annotation_rows": EXPECTED_FRAME_COUNT * len(SUBJECTS),
        "labels_initially_blank": True,
        "model_evidence_excluded": True,
        "independent_frame_level_estimate_established": False,
        "claim_ceiling": "Blinded review input package only. No action labels, onsets, mimicry pairs or latency are established.",
    }
    package_manifest["files_payload_sha256"] = canonical_sha256(package_manifest["files"])
    package_manifest_path = out / "package_manifest.json"
    package_manifest_path.write_text(
        json.dumps(package_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = {
        "status": "PASS_PACKAGE_BUILT",
        "frames": EXPECTED_FRAME_COUNT,
        "annotation_rows": EXPECTED_FRAME_COUNT * len(SUBJECTS),
        "frame_manifest_sha256": sha256_file(frame_manifest_path),
        "review_form_sha256_blank": sha256_file(form_path),
        "instructions_sha256": sha256_file(instructions_path),
        "package_manifest_sha256": sha256_file(package_manifest_path),
        "files_payload_sha256": package_manifest["files_payload_sha256"],
        "out_dir": str(out),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--frame-ledger", required=True, type=Path)
    parser.add_argument("--frame-dir", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    build(parse_args())
