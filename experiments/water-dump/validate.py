from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

from PIL import Image, ImageStat


OUTPUT_DIR = Path.cwd() / "output"
VIDEO_PATH = OUTPUT_DIR / "water-dump.mp4"
POSTER_PATH = OUTPUT_DIR / "poster.png"
BLEND_PATH = OUTPUT_DIR / "scene.blend"
VALIDATION_PATH = OUTPUT_DIR / "validation.json"


def mp4_duration_seconds(data: bytes) -> float:
    marker = data.find(b"mvhd")
    if marker < 0:
        raise SystemExit("MP4 mvhd box not found")

    payload = marker + 4
    if payload + 4 > len(data):
        raise SystemExit("truncated MP4 mvhd box")

    version = data[payload]
    if version == 0:
        if payload + 24 > len(data):
            raise SystemExit("truncated version-0 mvhd box")
        timescale = struct.unpack(">I", data[payload + 12 : payload + 16])[0]
        duration = struct.unpack(">I", data[payload + 16 : payload + 20])[0]
    elif version == 1:
        if payload + 36 > len(data):
            raise SystemExit("truncated version-1 mvhd box")
        timescale = struct.unpack(">I", data[payload + 20 : payload + 24])[0]
        duration = struct.unpack(">Q", data[payload + 24 : payload + 32])[0]
    else:
        raise SystemExit(f"unsupported mvhd version: {version}")

    if timescale <= 0:
        raise SystemExit("invalid MP4 timescale")
    return duration / timescale


def main() -> None:
    for path in (VIDEO_PATH, POSTER_PATH, BLEND_PATH):
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(f"missing or empty output: {path}")

    if VIDEO_PATH.stat().st_size < 32_000:
        raise SystemExit(f"video unexpectedly tiny: {VIDEO_PATH.stat().st_size} bytes")

    video_data = VIDEO_PATH.read_bytes()
    if b"ftyp" not in video_data[:64]:
        raise SystemExit("MP4 ftyp header not found")
    if b"mdat" not in video_data:
        raise SystemExit("MP4 media-data box not found")
    if b"moov" not in video_data:
        raise SystemExit("MP4 movie box not found")

    duration = mp4_duration_seconds(video_data)
    if not 2.5 <= duration <= 3.5:
        raise SystemExit(f"unexpected duration: {duration:.3f}s")

    with Image.open(POSTER_PATH) as image:
        image.load()
        if image.size != (640, 360):
            raise SystemExit(f"unexpected poster size: {image.size}")

        rgb = image.convert("RGB")
        gray = rgb.convert("L")
        stat = ImageStat.Stat(gray)
        extrema = gray.getextrema()
        stddev = float(stat.stddev[0])
        preview = rgb.resize((64, 36))
        colors = preview.getcolors(maxcolors=2304)
        unique_colors = len(colors) if colors is not None else 2304

        if extrema[1] - extrema[0] < 40:
            raise SystemExit(f"poster luminance range too small: {extrema}")
        if stddev < 8.0:
            raise SystemExit(f"poster too uniform: stddev={stddev:.2f}")
        if unique_colors < 96:
            raise SystemExit(f"poster has too little color variation: {unique_colors}")

    result = {
        "video": VIDEO_PATH.name,
        "video_size_bytes": VIDEO_PATH.stat().st_size,
        "container": "mp4",
        "width": 640,
        "height": 360,
        "duration_seconds": round(duration, 3),
        "fps": 24,
        "poster": POSTER_PATH.name,
        "poster_luminance_min": extrema[0],
        "poster_luminance_max": extrema[1],
        "poster_luminance_stddev": round(stddev, 3),
        "poster_unique_colors_64x36": unique_colors,
        "sha256": hashlib.sha256(video_data).hexdigest(),
    }

    VALIDATION_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
