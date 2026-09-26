from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: python3 scripts/make_preview.py <input_png> <output_jpg>")
        return 2

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])

    if not src.exists():
        raise SystemExit(f"input missing: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src) as image:
        image = image.convert("RGB")
        image.thumbnail((512, 512))
        image.save(dst, format="JPEG", quality=90, optimize=True)

    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
