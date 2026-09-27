from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path.cwd()
BASE = ROOT / "output" / "sph-blender-sequence"
SEQUENCE = BASE / "sequence"
BLENDER = BASE / "blender"


def obj_counts(path: Path):
    vertices = 0
    faces = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("v "):
                vertices += 1
            elif line.startswith("f "):
                faces += 1
    return vertices, faces


manifest = json.loads((SEQUENCE / "surface-sequence.json").read_text(encoding="utf-8"))
records = manifest["frames"]
if len(records) < 3:
    raise SystemExit(f"expected >=3 frames, got {len(records)}")

for record in records:
    path = SEQUENCE / "surfaces" / record["surface_obj"]
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"missing/empty surface: {path}")
    vertices, faces = obj_counts(path)
    if vertices != int(record["vertices"]) or faces != int(record["faces"]):
        raise SystemExit(
            f"OBJ count mismatch for {path.name}: "
            f"manifest={record['vertices']}/{record['faces']} "
            f"actual={vertices}/{faces}"
        )

blend = BLENDER / "surface-sequence.blend"
preview = BLENDER / "preview.png"
video = BLENDER / "surface-sequence.mp4"
blend_validation = BLENDER / "blend-validation.json"

for path, minimum in (
    (blend, 100_000),
    (preview, 10_000),
    (video, 10_000),
    (blend_validation, 100),
):
    if not path.is_file() or path.stat().st_size < minimum:
        raise SystemExit(
            f"missing or too-small output: {path} "
            f"size={path.stat().st_size if path.exists() else 0}"
        )

blend_check = json.loads(blend_validation.read_text(encoding="utf-8"))
if blend_check.get("errors"):
    raise SystemExit(f"blend validation errors: {blend_check['errors']}")
if int(blend_check.get("frames", 0)) != len(records):
    raise SystemExit("blend validation frame count mismatch")

probe = {}
try:
    raw = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames,r_frame_rate,duration,width,height",
            "-of",
            "json",
            str(video),
        ],
        text=True,
    )
    probe = json.loads(raw)
except (FileNotFoundError, subprocess.CalledProcessError, json.JSONDecodeError):
    probe = {"warning": "ffprobe unavailable or failed"}

if "streams" in probe and probe["streams"]:
    stream = probe["streams"][0]
    count = stream.get("nb_read_frames")
    if count not in (None, "N/A") and int(count) != len(records):
        raise SystemExit(
            f"video frame count mismatch: expected {len(records)}, got {count}"
        )

result = {
    "surface_frames": len(records),
    "source_frames": [int(r["source_frame"]) for r in records],
    "vertices_min": min(int(r["vertices"]) for r in records),
    "vertices_max": max(int(r["vertices"]) for r in records),
    "faces_min": min(int(r["faces"]) for r in records),
    "faces_max": max(int(r["faces"]) for r in records),
    "surface_bytes_total": sum(int(r["bytes"]) for r in records),
    "blend_bytes": blend.stat().st_size,
    "preview_bytes": preview.stat().st_size,
    "video_bytes": video.stat().st_size,
    "video_probe": probe,
}
(BASE / "validation.json").write_text(
    json.dumps(result, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(result, indent=2))
