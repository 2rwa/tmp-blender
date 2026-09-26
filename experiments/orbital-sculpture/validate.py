from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageStat


def validate(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"render missing: {path}")

    size_bytes = path.stat().st_size
    if size_bytes < 20_000:
        raise SystemExit(f"render suspiciously small: {size_bytes} bytes")

    with Image.open(path) as image:
        image.load()
        if image.size != (640, 640):
            raise SystemExit(f"unexpected render size: {image.size}")

        rgb = image.convert("RGB")
        gray = rgb.convert("L")
        stat = ImageStat.Stat(gray)
        extrema = gray.getextrema()
        stddev = float(stat.stddev[0])
        mean = float(stat.mean[0])

        # Downsample for a stable complexity check that stays cheap.
        preview = rgb.resize((64, 64))
        colors = preview.getcolors(maxcolors=4096)
        unique_colors = len(colors) if colors is not None else 4096

        if extrema[1] - extrema[0] < 45:
            raise SystemExit(f"insufficient luminance range: {extrema}")
        if stddev < 10.0:
            raise SystemExit(f"render looks too uniform: stddev={stddev:.2f}")
        if unique_colors < 128:
            raise SystemExit(f"render has too little visual variation: {unique_colors} colors")

    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "path": str(path),
        "size_bytes": size_bytes,
        "width": 640,
        "height": 640,
        "luminance_min": extrema[0],
        "luminance_max": extrema[1],
        "luminance_mean": round(mean, 3),
        "luminance_stddev": round(stddev, 3),
        "unique_colors_64x64": unique_colors,
        "sha256": digest,
    }


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "output/render.png")
    result = validate(path)
    output = path.parent / "validation.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
