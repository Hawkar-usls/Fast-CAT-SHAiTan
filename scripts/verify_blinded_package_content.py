#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from fastcat.blinded_package_identity import verify_package_zip


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--identity", required=True, type=Path)
    parser.add_argument("--zip", required=True, dest="zip_path", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    identity = json.loads(args.identity.read_text(encoding="utf-8"))
    if not isinstance(identity, dict):
        raise SystemExit("IDENTITY_JSON_OBJECT_REQUIRED")
    report = verify_package_zip(zip_path=args.zip_path, identity=identity)
    report["content_identity_file_sha256"] = sha256_file(args.identity)
    report["content_identity_file"] = str(args.identity)
    report["transport_file"] = str(args.zip_path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "EXACT_CANONICAL_CONTENT_MATCH" else 1


if __name__ == "__main__":
    raise SystemExit(main())
