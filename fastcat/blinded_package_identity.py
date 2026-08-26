from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


MATCH_STATUS = "EXACT_CANONICAL_CONTENT_MATCH"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _validate_manifest(
    *, manifest_bytes: bytes, identity: dict[str, Any]
) -> tuple[list[str], list[dict[str, Any]]]:
    failures: list[str] = []
    expected = identity["canonical_package"]
    if sha256_bytes(manifest_bytes) != expected["package_manifest_file_sha256"]:
        failures.append("PACKAGE_MANIFEST_FILE_SHA256_MISMATCH")
    try:
        manifest = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return failures + ["PACKAGE_MANIFEST_JSON_INVALID"], []
    if not isinstance(manifest, dict):
        return failures + ["PACKAGE_MANIFEST_NOT_OBJECT"], []
    if manifest.get("schema") != expected["package_manifest_schema"]:
        failures.append("PACKAGE_MANIFEST_SCHEMA_MISMATCH")
    if manifest.get("source_id") != identity.get("source_id"):
        failures.append("PACKAGE_MANIFEST_SOURCE_ID_MISMATCH")
    if manifest.get("labels_initially_blank") is not True:
        failures.append("LABELS_INITIALLY_BLANK_NOT_TRUE")
    if manifest.get("model_evidence_excluded") is not True:
        failures.append("MODEL_EVIDENCE_EXCLUDED_NOT_TRUE")
    if manifest.get("independent_frame_level_estimate_established") is not False:
        failures.append("INDEPENDENT_FRAME_LEVEL_ESTIMATE_NOT_FALSE")
    files = manifest.get("files")
    if not isinstance(files, list):
        return failures + ["PACKAGE_MANIFEST_FILES_INVALID"], []
    if len(files) != int(expected["payload_file_count"]):
        failures.append("PAYLOAD_FILE_COUNT_MISMATCH")
    payload_sha = sha256_bytes(canonical_bytes(files))
    if payload_sha != manifest.get("files_payload_sha256"):
        failures.append("PACKAGE_MANIFEST_FILES_PAYLOAD_SELF_HASH_MISMATCH")
    if payload_sha != expected["files_payload_sha256"]:
        failures.append("FILES_PAYLOAD_SHA256_NOT_CANONICAL")
    if manifest.get("protocol_sha256") != expected["protocol_sha256"]:
        failures.append("PACKAGE_PROTOCOL_SHA256_MISMATCH")
    if manifest.get("frame_ledger_sha256") != expected["frame_ledger_sha256"]:
        failures.append("PACKAGE_FRAME_LEDGER_SHA256_MISMATCH")
    return failures, files


def _validate_relpath(path: str) -> bool:
    if not path or "\\" in path:
        return False
    pure = PurePosixPath(path)
    return (
        not pure.is_absolute()
        and ".." not in pure.parts
        and str(pure) == path
        and path != "package_manifest.json"
    )


def verify_package_zip(
    *, zip_path: str | Path, identity: dict[str, Any]
) -> dict[str, Any]:
    zip_path = Path(zip_path)
    failures: list[str] = []
    transport_sha = sha256_file(zip_path)
    try:
        archive = zipfile.ZipFile(zip_path)
    except (OSError, zipfile.BadZipFile):
        return {
            "schema": "Fast-CAT/PILOT-001/blinded-review-content-verification/v1.0",
            "status": "FAIL",
            "failures": ["TRANSPORT_ZIP_INVALID"],
            "transport_zip_sha256": transport_sha,
            "independent_frame_level_estimate_established": False,
        }
    with archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        if len(names) != len(set(names)):
            failures.append("DUPLICATE_ZIP_MEMBER_NAMES")
        roots: list[str] = []
        if "package/package_manifest.json" in names:
            roots.append("package/")
        if "package_manifest.json" in names:
            roots.append("")
        if len(roots) != 1:
            return {
                "schema": "Fast-CAT/PILOT-001/blinded-review-content-verification/v1.0",
                "status": "FAIL",
                "failures": sorted(set(failures + ["PACKAGE_ROOT_AMBIGUOUS_OR_MISSING"])),
                "transport_zip_sha256": transport_sha,
                "independent_frame_level_estimate_established": False,
            }
        prefix = roots[0]
        manifest_member = prefix + "package_manifest.json"
        manifest_bytes = archive.read(manifest_member)
        manifest_failures, files = _validate_manifest(
            manifest_bytes=manifest_bytes, identity=identity
        )
        failures.extend(manifest_failures)

        listed_members: set[str] = set()
        seen_paths: set[str] = set()
        for index, item in enumerate(files):
            code = f"FILE_{index}"
            if not isinstance(item, dict):
                failures.append(f"{code}:ENTRY_NOT_OBJECT")
                continue
            relpath = str(item.get("path", ""))
            if not _validate_relpath(relpath):
                failures.append(f"{code}:PATH_INVALID")
                continue
            if relpath in seen_paths:
                failures.append(f"{code}:DUPLICATE_PATH")
                continue
            seen_paths.add(relpath)
            member = prefix + relpath
            listed_members.add(member)
            if member not in names:
                failures.append(f"{code}:MISSING:{relpath}")
                continue
            payload = archive.read(member)
            try:
                expected_size = int(item.get("byte_length", -1))
            except (TypeError, ValueError):
                expected_size = -1
            if len(payload) != expected_size:
                failures.append(f"{code}:BYTE_LENGTH_MISMATCH:{relpath}")
            if sha256_bytes(payload) != str(item.get("sha256", "")):
                failures.append(f"{code}:SHA256_MISMATCH:{relpath}")

        # Canonical identity covers the entire non-directory archive surface,
        # not only members under the selected package prefix. A transport may
        # repack compression/container metadata, but it may not smuggle model
        # evidence or any other file beside the manifest + manifest-listed bytes.
        expected_members = listed_members | {manifest_member}
        actual_members = set(names)
        extras = sorted(actual_members - expected_members)
        missing = sorted(expected_members - actual_members)
        if extras:
            failures.append("EXTRA_ARCHIVE_MEMBERS:" + ",".join(extras))
        if missing:
            failures.append("LISTED_FILES_MISSING:" + ",".join(missing))

        expected = identity["canonical_package"]
        anchors = {
            "frame_manifest.json": "frame_manifest_file_sha256",
            "review_form.csv": "blank_review_form_sha256",
            "REVIEW_INSTRUCTIONS.md": "instructions_file_sha256",
        }
        for relpath, key in anchors.items():
            member = prefix + relpath
            if member not in names:
                failures.append(f"ANCHOR_MISSING:{relpath}")
            elif sha256_bytes(archive.read(member)) != expected[key]:
                failures.append(f"ANCHOR_SHA256_MISMATCH:{relpath}")

    failures = sorted(set(failures))
    original_transport_sha = str(
        identity.get("original_transport", {}).get("artifact_zip_sha256", "")
    )
    return {
        "schema": "Fast-CAT/PILOT-001/blinded-review-content-verification/v1.0",
        "status": MATCH_STATUS if not failures else "FAIL",
        "failures": failures,
        "content_identity_schema": identity.get("schema"),
        "content_identity_sha256": sha256_bytes(canonical_bytes(identity)),
        "package_manifest_file_sha256": identity["canonical_package"][
            "package_manifest_file_sha256"
        ],
        "files_payload_sha256": identity["canonical_package"][
            "files_payload_sha256"
        ],
        "verified_payload_files": len(files) if not failures else None,
        "transport_zip_sha256": transport_sha,
        "original_transport_match": bool(
            original_transport_sha and transport_sha == original_transport_sha
        ),
        "independent_frame_level_estimate_established": False,
        "claim_ceiling": "Exact blinded package content verification only; no reviewer independence, action label, onset, mimicry or latency claim is established.",
    }
