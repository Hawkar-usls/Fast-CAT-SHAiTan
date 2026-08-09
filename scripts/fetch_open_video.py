#!/usr/bin/env python3
"""Fetch one openly licensed Wikimedia candidate and emit an integrity receipt.

Raw media is written below data/raw/ and is intentionally gitignored. The receipt
records source metadata, the exact byte SHA-256 and ffprobe stream metadata when
ffprobe is installed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "open_video_sources.json"
RAW_DIR = ROOT / "data" / "raw"
RECEIPT_DIR = ROOT / "data" / "receipts"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_source(source_id: str) -> dict[str, Any]:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for source in data["sources"]:
        if source["source_id"] == source_id:
            return source
    known = ", ".join(s["source_id"] for s in data["sources"])
    raise SystemExit(f"unknown source_id={source_id!r}; known: {known}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def ffprobe(path: Path) -> dict[str, Any] | None:
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    cmd = [
        exe,
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(path),
    ]
    completed = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)


def fetch(source: dict[str, Any]) -> tuple[Path, str]:
    title = source["title"]
    redirect = "https://commons.wikimedia.org/wiki/Special:Redirect/file/" + urllib.parse.quote(title, safe="")
    out_dir = RAW_DIR / source["source_id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / Path(title).name

    request = urllib.request.Request(
        redirect,
        headers={"User-Agent": "Fast-CAT-SHAiTan/0.1 research-prototype"},
    )
    with urllib.request.urlopen(request, timeout=120) as response, out_path.open("wb") as handle:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            handle.write(block)

    return out_path, redirect


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source_id")
    args = parser.parse_args()

    source = load_source(args.source_id)
    path, download_url = fetch(source)
    digest = sha256_file(path)
    probe = ffprobe(path)

    receipt = {
        "schema_version": "1.0",
        "source_id": source["source_id"],
        "source_page": source["source_page"],
        "source_license": source["license"],
        "download_url": download_url,
        "fetched_at": now_iso(),
        "local_filename": path.name,
        "byte_length": path.stat().st_size,
        "raw_media_sha256": digest,
        "ffprobe": probe,
        "admission": "UNREVIEWED_SOURCE_FETCH",
    }

    RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
    receipt_path = RECEIPT_DIR / f"{source['source_id']}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps(receipt, indent=2, sort_keys=True))
    print(f"receipt={receipt_path}")
    print(f"raw_media={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
