from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

from PIL import Image, ImageStat


OUTPUT = Path.cwd() / "output"
VIDEO = OUTPUT / "fluid-dam-break.mp4"
POSTER = OUTPUT / "poster.png"
SIM_BLEND = OUTPUT / "fluid-sim.blend"
RESULT_BLEND = OUTPUT / "fluid-result.blend"
CACHE = OUTPUT / "fluid-cache"
VALIDATION = OUTPUT / "validation.json"


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
    for path in (VIDEO, POSTER, SIM_BLEND, RESULT_BLEND):
        if not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(f"missing or empty output: {path}")

    for blend in (SIM_BLEND, RESULT_BLEND):
        if blend.stat().st_size < 100_000:
            raise SystemExit(f"blend suspiciously small: {blend} ({blend.stat().st_size} bytes)")

    cache_files = [p for p in CACHE.rglob("*") if p.is_file()]
    cache_bytes = sum(p.stat().st_size for p in cache_files)
    if not cache_files or cache_bytes < 100_000:
        raise SystemExit(f"fluid cache missing or too small: {cache_bytes} bytes")

    data = VIDEO.read_bytes()
    if VIDEO.stat().st_size < 48_000:
        raise SystemExit(f"video unexpectedly tiny: {VIDEO.stat().st_size} bytes")
    for marker in (b"ftyp", b"mdat", b"moov"):
        if marker not in data:
            raise SystemExit(f"MP4 marker missing: {marker!r}")

    duration = mp4_duration_seconds(data)
    if not 1.5 <= duration <= 2.2:
        raise SystemExit(f"unexpected duration: {duration:.3f}s")

    with Image.open(POSTER) as image:
        image.load()
        if image.size != (640, 360):
            raise SystemExit(f"unexpected poster size: {image.size}")

        rgb = image.convert("RGB")
        gray = rgb.convert("L")
        stat = ImageStat.Stat(gray)
        extrema = gray.getextrema()
        stddev = float(stat.stddev[0])
        small = rgb.resize((64, 36))
        colors = small.getcolors(maxcolors=2304)
        unique_colors = len(colors) if colors is not None else 2304

        blueish = 0
        total = rgb.width * rgb.height
        for r, g, b in rgb.getdata():
            if b >= 70 and b > r * 1.15 and b >= g * 0.95:
                blueish += 1
        blue_ratio = blueish / total

        if extrema[1] - extrema[0] < 50:
            raise SystemExit(f"poster luminance range too small: {extrema}")
        if stddev < 10:
            raise SystemExit(f"poster too uniform: stddev={stddev:.2f}")
        if unique_colors < 128:
            raise SystemExit(f"poster color variation too small: {unique_colors}")
        if blue_ratio < 0.003:
            raise SystemExit(f"too few blue water pixels: {blue_ratio:.6f}")

    result = {
        "video": VIDEO.name,
        "video_size_bytes": VIDEO.stat().st_size,
        "container": "mp4",
        "width": 640,
        "height": 360,
        "duration_seconds": round(duration, 3),
        "fps": 24,
        "poster": POSTER.name,
        "poster_luminance_min": extrema[0],
        "poster_luminance_max": extrema[1],
        "poster_luminance_stddev": round(stddev, 3),
        "poster_unique_colors_64x36": unique_colors,
        "blue_pixel_ratio": round(blue_ratio, 6),
        "fluid_cache_files": len(cache_files),
        "fluid_cache_bytes": cache_bytes,
        "fluid_sim_blend_bytes": SIM_BLEND.stat().st_size,
        "fluid_result_blend_bytes": RESULT_BLEND.stat().st_size,
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    VALIDATION.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
