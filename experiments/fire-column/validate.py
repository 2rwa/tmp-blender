from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

from PIL import Image, ImageStat


OUTPUT_DIR = Path.cwd() / "output"
VIDEO_PATH = OUTPUT_DIR / "fire-column.mp4"
POSTER_PATH = OUTPUT_DIR / "poster.png"
BLEND_PATH = OUTPUT_DIR / "scene.blend"
VALIDATION_PATH = OUTPUT_DIR / "validation.json"


def mp4_duration_seconds(data: bytes) -> float:
    marker = data.find(b"mvhd")
    if marker < 0:
        raise SystemExit("MP4 mvhd box not found")

    payload = marker + 4
    version = data[payload]
    if version == 0:
        timescale = struct.unpack(">I", data[payload + 12 : payload + 16])[0]
        duration = struct.unpack(">I", data[payload + 16 : payload + 20])[0]
    elif version == 1:
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
    for marker in (b"ftyp", b"mdat", b"moov"):
        if marker not in video_data:
            raise SystemExit(f"MP4 marker missing: {marker!r}")

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

        bright = 0
        warm = 0
        total = rgb.width * rgb.height
        for r, g, b in rgb.getdata():
            if max(r, g, b) >= 180:
                bright += 1
            if r >= 110 and r > g * 1.12 and g > b * 1.18:
                warm += 1

        bright_ratio = bright / total
        warm_ratio = warm / total

        if extrema[1] - extrema[0] < 80:
            raise SystemExit(f"poster luminance range too small: {extrema}")
        if stddev < 12.0:
            raise SystemExit(f"poster too uniform: stddev={stddev:.2f}")
        if bright_ratio < 0.002:
            raise SystemExit(f"too few bright flame pixels: {bright_ratio:.5f}")
        if warm_ratio < 0.005:
            raise SystemExit(f"too few warm flame pixels: {warm_ratio:.5f}")

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
        "bright_pixel_ratio": round(bright_ratio, 6),
        "warm_pixel_ratio": round(warm_ratio, 6),
        "sha256": hashlib.sha256(video_data).hexdigest(),
    }

    VALIDATION_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
