from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageStat


OUTPUT_DIR = Path.cwd() / "output"
VIDEO_PATH = OUTPUT_DIR / "water-dump.mp4"
POSTER_PATH = OUTPUT_DIR / "poster.png"
BLEND_PATH = OUTPUT_DIR / "scene.blend"
VALIDATION_PATH = OUTPUT_DIR / "validation.json"


def ffprobe(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def main() -> None:
    for path in (VIDEO_PATH, POSTER_PATH, BLEND_PATH):
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(f"missing or empty output: {path}")

    if VIDEO_PATH.stat().st_size < 100_000:
        raise SystemExit(f"video suspiciously small: {VIDEO_PATH.stat().st_size} bytes")

    info = ffprobe(VIDEO_PATH)
    streams = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    if not streams:
        raise SystemExit("no video stream found")
    stream = streams[0]

    width = int(stream.get("width", 0))
    height = int(stream.get("height", 0))
    if (width, height) != (640, 360):
        raise SystemExit(f"unexpected video dimensions: {(width, height)}")

    duration = float(stream.get("duration") or info.get("format", {}).get("duration") or 0.0)
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
        "width": width,
        "height": height,
        "duration_seconds": round(duration, 3),
        "fps": 24,
        "poster": POSTER_PATH.name,
        "poster_luminance_min": extrema[0],
        "poster_luminance_max": extrema[1],
        "poster_luminance_stddev": round(stddev, 3),
        "poster_unique_colors_64x36": unique_colors,
        "sha256": hashlib.sha256(VIDEO_PATH.read_bytes()).hexdigest(),
    }
    VALIDATION_PATH.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
