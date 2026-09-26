# SPDX-License-Identifier: MIT-0
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

from PIL import Image, ImageStat


OUTPUT = Path.cwd() / "output"
VIDEO = OUTPUT / "rigid-sphere-impact-1000-transparent-v2.mp4"
POSTER = OUTPUT / "poster.png"
SIM_BLEND = OUTPUT / "rigid-sim.blend"
RESULT_BLEND = OUTPUT / "rigid-result.blend"
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

    data = VIDEO.read_bytes()
    if VIDEO.stat().st_size < 80_000:
        raise SystemExit(f"video unexpectedly tiny: {VIDEO.stat().st_size} bytes")
    for marker in (b"ftyp", b"mdat", b"moov"):
        if marker not in data:
            raise SystemExit(f"MP4 marker missing: {marker!r}")

    duration = mp4_duration_seconds(data)
    if not 3.7 <= duration <= 4.3:
        raise SystemExit(f"unexpected duration: {duration:.3f}s")

    with Image.open(POSTER) as image:
        image.load()
        if image.size != (960, 540):
            raise SystemExit(f"unexpected poster size: {image.size}")

        rgb = image.convert("RGB")
        gray = rgb.convert("L")
        stat = ImageStat.Stat(gray)
        extrema = gray.getextrema()
        stddev = float(stat.stddev[0])

        bright = 0
        warm = 0
        cool = 0
        total = rgb.width * rgb.height
        for r, g, b in rgb.getdata():
            if max(r, g, b) >= 165:
                bright += 1
            if r >= 120 and r > g * 1.10 and g >= b * 0.80:
                warm += 1
            if b >= 95 and b > r * 1.05:
                cool += 1

        bright_ratio = bright / total
        warm_ratio = warm / total
        cool_ratio = cool / total

        if extrema[1] - extrema[0] < 45:
            raise SystemExit(f"poster luminance range too small: {extrema}")
        if stddev < 10.0:
            raise SystemExit(f"poster too uniform: stddev={stddev:.2f}")
        if bright_ratio < 0.002:
            raise SystemExit(f"poster too dark: {bright_ratio:.6f}")
        if warm_ratio < 0.0004:
            raise SystemExit(f"impact sphere not visible enough: {warm_ratio:.6f}")
        if cool_ratio < 0.004:
            raise SystemExit(f"cube field not visible enough: {cool_ratio:.6f}")

    result = {
        "video": VIDEO.name,
        "video_size_bytes": VIDEO.stat().st_size,
        "container": "mp4",
        "width": 960,
        "height": 540,
        "duration_seconds": round(duration, 3),
        "fps": 24,
        "poster": POSTER.name,
        "poster_frame": 44,
        "rigid_body_cubes": 1000,
        "impact_spheres": 1,
        "transparent_walls": 3,
        "rigid_substeps_per_frame": 12,
        "rigid_solver_iterations": 30,
        "poster_luminance_min": extrema[0],
        "poster_luminance_max": extrema[1],
        "poster_luminance_stddev": round(stddev, 3),
        "bright_pixel_ratio": round(bright_ratio, 6),
        "warm_pixel_ratio": round(warm_ratio, 6),
        "cool_pixel_ratio": round(cool_ratio, 6),
        "rigid_sim_blend_bytes": SIM_BLEND.stat().st_size,
        "rigid_result_blend_bytes": RESULT_BLEND.stat().st_size,
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    VALIDATION.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
