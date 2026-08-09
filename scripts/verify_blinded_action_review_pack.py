#!/usr/bin/env python3
"""Independently verify the PILOT_001 blinded action-review package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify(args: argparse.Namespace) -> dict[str, Any]:
    failures: list[str] = []
    pack = args.package_dir.resolve()
    ledger = json.loads(args.frame_ledger.read_text(encoding="utf-8"))
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))

    if protocol.get("schema") != "Fast-CAT/PILOT-001/blinded-review-package-protocol/v1.0":
        failures.append("PROTOCOL_SCHEMA_MISMATCH")
    if ledger.get("source_id") != EXPECTED_SOURCE_ID:
        failures.append("LEDGER_SOURCE_ID_MISMATCH")
    if ledger.get("source_media_sha256") != EXPECTED_RAW_SHA256:
        failures.append("LEDGER_RAW_SHA256_MISMATCH")
    if int(ledger.get("frame_count", -1)) != EXPECTED_FRAME_COUNT:
        failures.append("LEDGER_FRAME_COUNT_MISMATCH")
    if ledger.get("frame_pts_sha256") != EXPECTED_PTS_SHA256:
        failures.append("LEDGER_PTS_SHA256_MISMATCH")

    manifest_path = pack / "frame_manifest.json"
    form_path = pack / "review_form.csv"
    instructions_path = pack / "REVIEW_INSTRUCTIONS.md"
    package_manifest_path = pack / "package_manifest.json"
    for path in (manifest_path, form_path, instructions_path, package_manifest_path):
        if not path.is_file():
            failures.append(f"REQUIRED_FILE_MISSING:{path.name}")

    if failures:
        report = {"status": "FAIL", "failures": failures}
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2, sort_keys=True))
        return report

    frame_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    package_manifest = json.loads(package_manifest_path.read_text(encoding="utf-8"))

    allowed_frame_manifest_keys = {
        "schema",
        "source_id",
        "raw_media_sha256",
        "frame_count",
        "frame_pts_sha256",
        "frames",
        "contains_model_derived_fields",
        "claim_ceiling",
    }
    if set(frame_manifest) != allowed_frame_manifest_keys:
        failures.append("FRAME_MANIFEST_UNEXPECTED_FIELDS")
    if frame_manifest.get("contains_model_derived_fields") is not False:
        failures.append("MODEL_DERIVED_FIELD_FLAG_NOT_FALSE")
    if frame_manifest.get("source_id") != EXPECTED_SOURCE_ID:
        failures.append("FRAME_MANIFEST_SOURCE_ID_MISMATCH")
    if frame_manifest.get("raw_media_sha256") != EXPECTED_RAW_SHA256:
        failures.append("FRAME_MANIFEST_RAW_SHA256_MISMATCH")
    if frame_manifest.get("frame_pts_sha256") != EXPECTED_PTS_SHA256:
        failures.append("FRAME_MANIFEST_PTS_SHA256_MISMATCH")

    ledger_selected = ledger.get("selection", {}).get("selected", [])
    if len(ledger_selected) != EXPECTED_FRAME_COUNT:
        failures.append("LEDGER_NOT_FULL_RATE")
    ledger_by_index = {int(x["frame_index"]): x for x in ledger_selected}

    frames = frame_manifest.get("frames", [])
    if len(frames) != EXPECTED_FRAME_COUNT:
        failures.append("FRAME_MANIFEST_COUNT_MISMATCH")
    frame_dir = pack / "frames"
    actual_frame_files = sorted(frame_dir.glob("*.png")) if frame_dir.is_dir() else []
    if len(actual_frame_files) != EXPECTED_FRAME_COUNT:
        failures.append("PACKAGE_FRAME_FILE_COUNT_MISMATCH")

    expected_frame_fields = {"frame_index", "pts_s", "filename", "png_sha256", "rgb24_sha256"}
    for position, frame in enumerate(frames):
        if set(frame) != expected_frame_fields:
            failures.append(f"FRAME_{position}:UNEXPECTED_FIELDS")
            continue
        index = int(frame.get("frame_index", -1))
        if index != position:
            failures.append(f"FRAME_{position}:INDEX_SEQUENCE_MISMATCH")
        ledger_item = ledger_by_index.get(index)
        if ledger_item is None:
            failures.append(f"FRAME_{index}:NOT_IN_LEDGER")
            continue
        for key in ("pts_s", "filename", "png_sha256", "rgb24_sha256"):
            ledger_key = "png_filename" if key == "filename" else key
            if str(frame.get(key)) != str(ledger_item.get(ledger_key)):
                failures.append(f"FRAME_{index}:{key.upper()}_LEDGER_MISMATCH")
        frame_path = frame_dir / str(frame.get("filename", ""))
        if not frame_path.is_file():
            failures.append(f"FRAME_{index}:PNG_MISSING")
        elif sha256_file(frame_path) != frame.get("png_sha256"):
            failures.append(f"FRAME_{index}:PNG_SHA256_MISMATCH")

    expected_headers = [
        "source_id",
        "frame_index",
        "pts_s",
        "subject_id",
        "identity_confirmed",
        *LABEL_COLUMNS,
        "review_notes",
    ]
    with form_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_headers:
            failures.append("REVIEW_FORM_HEADERS_MISMATCH")
        rows = list(reader)
    if len(rows) != EXPECTED_FRAME_COUNT * len(SUBJECTS):
        failures.append("REVIEW_FORM_ROW_COUNT_MISMATCH")

    expected_pairs = [
        (frame_index, subject)
        for frame_index in range(EXPECTED_FRAME_COUNT)
        for subject in SUBJECTS
    ]
    actual_pairs = []
    for row_number, row in enumerate(rows):
        try:
            frame_index = int(row["frame_index"])
        except (KeyError, TypeError, ValueError):
            failures.append(f"ROW_{row_number}:FRAME_INDEX_INVALID")
            continue
        subject = str(row.get("subject_id", ""))
        actual_pairs.append((frame_index, subject))
        ledger_item = ledger_by_index.get(frame_index)
        if ledger_item is None:
            failures.append(f"ROW_{row_number}:FRAME_NOT_IN_LEDGER")
        else:
            if row.get("source_id") != EXPECTED_SOURCE_ID:
                failures.append(f"ROW_{row_number}:SOURCE_ID_MISMATCH")
            if str(row.get("pts_s")) != str(ledger_item.get("pts_s")):
                failures.append(f"ROW_{row_number}:PTS_MISMATCH")
        if row.get("identity_confirmed", "") != "":
            failures.append(f"ROW_{row_number}:IDENTITY_NOT_BLANK")
        for column in LABEL_COLUMNS:
            if row.get(column, "") != "":
                failures.append(f"ROW_{row_number}:{column}:LABEL_NOT_BLANK")
        if row.get("review_notes", "") != "":
            failures.append(f"ROW_{row_number}:NOTES_NOT_BLANK")
    if actual_pairs != expected_pairs:
        failures.append("REVIEW_FORM_ORDER_MISMATCH")

    allowed_root_names = {
        "frames",
        "frame_manifest.json",
        "review_form.csv",
        "REVIEW_INSTRUCTIONS.md",
        "package_manifest.json",
    }
    actual_root_names = {p.name for p in pack.iterdir()}
    if actual_root_names != allowed_root_names:
        failures.append("PACKAGE_ROOT_CONTAINS_UNEXPECTED_FILES")

    listed_files = package_manifest.get("files", [])
    listed_paths = set()
    for item in listed_files:
        rel = str(item.get("path", ""))
        listed_paths.add(rel)
        path = pack / rel
        if not path.is_file():
            failures.append(f"PACKAGE_MANIFEST_FILE_MISSING:{rel}")
            continue
        if int(item.get("byte_length", -1)) != path.stat().st_size:
            failures.append(f"PACKAGE_MANIFEST_SIZE_MISMATCH:{rel}")
        if str(item.get("sha256", "")) != sha256_file(path):
            failures.append(f"PACKAGE_MANIFEST_SHA256_MISMATCH:{rel}")
    expected_listed_paths = {
        "frame_manifest.json",
        "review_form.csv",
        "REVIEW_INSTRUCTIONS.md",
        *{f"frames/{p.name}" for p in actual_frame_files},
    }
    if listed_paths != expected_listed_paths:
        failures.append("PACKAGE_MANIFEST_FILE_SET_MISMATCH")
    if package_manifest.get("labels_initially_blank") is not True:
        failures.append("PACKAGE_LABELS_BLANK_FLAG_MISSING")
    if package_manifest.get("model_evidence_excluded") is not True:
        failures.append("PACKAGE_MODEL_EVIDENCE_EXCLUDED_FLAG_MISSING")
    if package_manifest.get("independent_frame_level_estimate_established") is not False:
        failures.append("PACKAGE_CLAIM_CEILING_VIOLATION")

    report = {
        "schema": "Fast-CAT/PILOT-001/blinded-review-package-verifier/v1.0",
        "status": "PASS" if not failures else "FAIL",
        "failures": failures,
        "frames_verified": len(frames),
        "annotation_rows_verified_blank": len(rows),
        "frame_manifest_sha256": sha256_file(manifest_path),
        "review_form_sha256_blank": sha256_file(form_path),
        "instructions_sha256": sha256_file(instructions_path),
        "package_manifest_sha256": sha256_file(package_manifest_path),
        "model_evidence_excluded": not failures,
        "independent_frame_level_estimate_established": False,
        "claim_ceiling": "Independent package-structure verification only; no action labels or latency result.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--frame-ledger", required=True, type=Path)
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    result = verify(parse_args())
    raise SystemExit(0 if result["status"] == "PASS" else 1)
