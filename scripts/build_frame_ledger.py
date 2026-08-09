#!/usr/bin/env python3
"""Build a deterministic PILOT_001 decoded-frame ledger and visual review pack.

Scientific boundary:
- source PTS is authoritative;
- selected PNGs are review aids only;
- pixel identity is SHA-256 over decoded RGB24 bytes;
- this script does not infer cat identity, landmarks, CatFACS actions, or latency.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


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


def run_json(cmd: list[str]) -> dict[str, Any]:
    raw = subprocess.check_output(cmd)
    return json.loads(raw.decode("utf-8"))


def ffprobe_stream(video: Path) -> dict[str, Any]:
    probe = run_json(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_streams",
            "-of",
            "json",
            str(video),
        ]
    )
    streams = probe.get("streams", [])
    if len(streams) != 1:
        raise RuntimeError(f"EXPECTED_ONE_VIDEO_STREAM:{len(streams)}")
    return streams[0]


def ffprobe_frames(video: Path) -> list[dict[str, Any]]:
    probe = run_json(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_frames",
            "-show_entries",
            "frame=best_effort_timestamp_time,pkt_dts_time,key_frame,pict_type",
            "-of",
            "json",
            str(video),
        ]
    )
    frames = probe.get("frames", [])
    if not frames:
        raise RuntimeError("NO_DECODED_VIDEO_FRAMES")
    return frames


def pts_text(frame: dict[str, Any]) -> str:
    value = frame.get("best_effort_timestamp_time")
    if value in (None, ""):
        value = frame.get("pkt_dts_time")
    if value in (None, ""):
        raise RuntimeError("FRAME_PTS_MISSING")
    try:
        d = Decimal(str(value))
    except InvalidOperation as exc:
        raise RuntimeError(f"FRAME_PTS_INVALID:{value}") from exc
    if not d.is_finite():
        raise RuntimeError(f"FRAME_PTS_NONFINITE:{value}")
    return str(value)


def validate_pts_monotonic(frame_pts: list[dict[str, Any]]) -> None:
    last: Decimal | None = None
    for entry in frame_pts:
        current = Decimal(entry["pts_s"])
        if last is not None and current <= last:
            raise RuntimeError(
                f"PTS_NOT_STRICTLY_INCREASING:{entry['frame_index']}:{current}<={last}"
            )
        last = current


def select_indices(frame_count: int, step_frames: int) -> list[int]:
    if frame_count <= 0:
        raise ValueError("FRAME_COUNT_MUST_BE_POSITIVE")
    if step_frames <= 0:
        raise ValueError("STEP_FRAMES_MUST_BE_POSITIVE")
    selected = list(range(0, frame_count, step_frames))
    final_index = frame_count - 1
    if selected[-1] != final_index:
        selected.append(final_index)
    return selected


def decoded_rgb24(video: Path, frame_index: int, width: int, height: int) -> bytes:
    select_expr = f"select=eq(n\\,{frame_index})"
    raw = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(video),
            "-vf",
            select_expr,
            "-frames:v",
            "1",
            "-an",
            "-sn",
            "-dn",
            "-pix_fmt",
            "rgb24",
            "-f",
            "rawvideo",
            "pipe:1",
        ]
    )
    expected = width * height * 3
    if len(raw) != expected:
        raise RuntimeError(
            f"RGB24_BYTE_LENGTH_MISMATCH:f{frame_index}:{len(raw)}!={expected}"
        )
    return raw


def extract_png(video: Path, frame_index: int, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    select_expr = f"select=eq(n\\,{frame_index})"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(video),
            "-vf",
            select_expr,
            "-frames:v",
            "1",
            "-an",
            "-sn",
            "-dn",
            str(out_path),
        ],
        check=True,
    )
    if not out_path.exists() or out_path.stat().st_size <= 0:
        raise RuntimeError(f"PNG_EXTRACTION_FAILED:{frame_index}")


def make_contact_sheets(
    selected: list[dict[str, Any]],
    frame_dir: Path,
    sheet_dir: Path,
    *,
    columns: int = 4,
    rows: int = 5,
    thumb_w: int = 300,
) -> list[dict[str, Any]]:
    sheet_dir.mkdir(parents=True, exist_ok=True)
    per_page = columns * rows
    font = ImageFont.load_default()
    page_records: list[dict[str, Any]] = []

    for page_index in range((len(selected) + per_page - 1) // per_page):
        page_items = selected[page_index * per_page : (page_index + 1) * per_page]
        rendered: list[tuple[Image.Image, str]] = []
        max_tile_h = 0
        for entry in page_items:
            image = Image.open(frame_dir / entry["png_filename"]).convert("RGB")
            ratio = thumb_w / image.width
            thumb_h = max(1, round(image.height * ratio))
            thumb = image.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            label = f"f{entry['frame_index']:06d}  PTS={entry['pts_s']} s"
            rendered.append((thumb, label))
            max_tile_h = max(max_tile_h, thumb_h + 24)

        canvas_w = columns * thumb_w
        canvas_h = rows * max_tile_h
        canvas = Image.new("RGB", (canvas_w, canvas_h), "white")
        draw = ImageDraw.Draw(canvas)
        for slot, (thumb, label) in enumerate(rendered):
            col = slot % columns
            row = slot // columns
            x = col * thumb_w
            y = row * max_tile_h
            canvas.paste(thumb, (x, y))
            draw.rectangle((x, y + thumb.height, x + thumb_w, y + max_tile_h), fill="white")
            draw.text((x + 4, y + thumb.height + 4), label, fill="black", font=font)

        page_path = sheet_dir / f"contact_sheet_{page_index + 1:02d}.png"
        canvas.save(page_path, format="PNG", optimize=False)
        page_records.append(
            {
                "page": page_index + 1,
                "filename": str(page_path.name),
                "sha256": sha256_file(page_path),
                "frame_indices": [x["frame_index"] for x in page_items],
            }
        )
    return page_records


def build(args: argparse.Namespace) -> dict[str, Any]:
    video = args.video.resolve()
    out_dir = args.out_dir.resolve()
    frame_dir = out_dir / "frames"
    sheet_dir = out_dir / "contact_sheets"
    out_dir.mkdir(parents=True, exist_ok=True)
    frame_dir.mkdir(parents=True, exist_ok=True)

    stream = ffprobe_stream(video)
    width = int(stream.get("width", 0))
    height = int(stream.get("height", 0))
    if width <= 0 or height <= 0:
        raise RuntimeError("VIDEO_DIMENSIONS_INVALID")

    raw_frames = ffprobe_frames(video)
    frame_pts: list[dict[str, Any]] = []
    for index, frame in enumerate(raw_frames):
        frame_pts.append(
            {
                "frame_index": index,
                "pts_s": pts_text(frame),
                "key_frame": int(frame.get("key_frame", 0)),
                "pict_type": str(frame.get("pict_type", "")),
            }
        )
    validate_pts_monotonic(frame_pts)

    deltas_ms = [
        float((Decimal(b["pts_s"]) - Decimal(a["pts_s"])) * Decimal(1000))
        for a, b in zip(frame_pts, frame_pts[1:])
    ]
    selected_indices = select_indices(len(frame_pts), args.step_frames)

    selected_records: list[dict[str, Any]] = []
    for index in selected_indices:
        pts = frame_pts[index]["pts_s"]
        pts_ms = int(round(float(Decimal(pts) * Decimal(1000))))
        png_name = f"f{index:06d}_pts{pts_ms:+09d}ms.png"
        png_path = frame_dir / png_name

        rgb = decoded_rgb24(video, index, width, height)
        extract_png(video, index, png_path)
        selected_records.append(
            {
                "frame_index": index,
                "pts_s": pts,
                "rgb24_sha256": hashlib.sha256(rgb).hexdigest(),
                "rgb24_byte_length": len(rgb),
                "png_filename": png_name,
                "png_sha256": sha256_file(png_path),
            }
        )

    sheets = make_contact_sheets(selected_records, frame_dir, sheet_dir)

    report = {
        "schema": "Fast-CAT/PILOT-001/decoded-frame-ledger/v1.0",
        "source_id": args.source_id,
        "source_media_sha256": sha256_file(video),
        "decoder": {
            "ffmpeg_version_first_line": subprocess.check_output(
                ["ffmpeg", "-version"], text=True
            ).splitlines()[0],
            "ffprobe_version_first_line": subprocess.check_output(
                ["ffprobe", "-version"], text=True
            ).splitlines()[0],
            "pixel_format_for_identity": "rgb24",
        },
        "stream": {
            "codec_name": stream.get("codec_name"),
            "width": width,
            "height": height,
            "avg_frame_rate": stream.get("avg_frame_rate"),
            "r_frame_rate": stream.get("r_frame_rate"),
            "time_base": stream.get("time_base"),
        },
        "frame_count": len(frame_pts),
        "frame_pts": frame_pts,
        "frame_pts_sha256": canonical_sha256(frame_pts),
        "pts_delta_ms": {
            "min": min(deltas_ms) if deltas_ms else None,
            "median": statistics.median(deltas_ms) if deltas_ms else None,
            "max": max(deltas_ms) if deltas_ms else None,
        },
        "selection": {
            "step_frames": args.step_frames,
            "rule": "frame 0, every step_frames frame, and final decoded frame",
            "selected_count": len(selected_records),
            "selected": selected_records,
        },
        "contact_sheets": sheets,
        "claim_ceiling": "Decoded-frame timing and pixel identity only. No cat identity, landmark, facial-action, mimicry, or latency claim is established.",
    }
    report["ledger_payload_sha256"] = canonical_sha256(
        {
            "source_id": report["source_id"],
            "source_media_sha256": report["source_media_sha256"],
            "stream": report["stream"],
            "frame_count": report["frame_count"],
            "frame_pts_sha256": report["frame_pts_sha256"],
            "selection": report["selection"],
        }
    )

    out_path = out_dir / "frame_ledger.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "source_id": args.source_id,
        "frame_count": len(frame_pts),
        "selected_count": len(selected_records),
        "frame_pts_sha256": report["frame_pts_sha256"],
        "ledger_payload_sha256": report["ledger_payload_sha256"],
        "out": str(out_path),
    }, indent=2, sort_keys=True))
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--step-frames", required=True, type=int)
    parser.add_argument("--out-dir", required=True, type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    build(parse_args())
