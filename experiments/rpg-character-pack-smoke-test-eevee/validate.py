from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageStat

EXPERIMENT = "rpg-character-pack-smoke-test-eevee"


def validate_preview(path):
    if not path.exists():
        raise SystemExit(f"preview missing: {path}")
    if path.stat().st_size < 12000:
        raise SystemExit(f"preview suspiciously small: {path.stat().st_size}")
    with Image.open(path) as image:
        image.load()
        if image.size != (480, 360):
            raise SystemExit(f"unexpected preview size: {image.size}")
        gray = image.convert("L")
        stat = ImageStat.Stat(gray)
        extrema = gray.getextrema()
        mean = float(stat.mean[0])
        stddev = float(stat.stddev[0])
        if extrema[1] - extrema[0] < 55:
            raise SystemExit(f"insufficient luminance range: {extrema}")
        if stddev < 12.0:
            raise SystemExit(f"preview too uniform: {stddev:.2f}")
    return {
        "size_bytes": path.stat().st_size,
        "luminance_min": extrema[0],
        "luminance_max": extrema[1],
        "luminance_mean": round(mean, 3),
        "luminance_stddev": round(stddev, 3),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def validate_video(path):
    if not path.exists():
        raise SystemExit(f"video missing: {path}")
    # Idle/attack animation plus a mostly static studio stage compresses very well.
    # Keep this as a coarse circuit breaker; character semantics are validated below.
    if path.stat().st_size < 15000:
        raise SystemExit(f"video suspiciously small: {path.stat().st_size}")
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,avg_frame_rate,nb_frames",
            "-show_entries", "format=size,duration",
            "-of", "json", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(proc.stdout)
    stream = (data.get("streams") or [{}])[0]
    fmt = data.get("format") or {}
    width = int(stream.get("width", 0))
    height = int(stream.get("height", 0))
    duration = float(fmt.get("duration") or 0.0)
    if (width, height) != (480, 360):
        raise SystemExit(f"unexpected movie dimensions: {(width, height)}")
    if not (5.5 <= duration <= 6.5):
        raise SystemExit(f"unexpected movie duration: {duration}")
    return {
        "size_bytes": path.stat().st_size,
        "duration_seconds": round(duration, 3),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "nb_frames": stream.get("nb_frames"),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def validate_report(report_path, blend_path):
    if not report_path.exists():
        raise SystemExit(f"report missing: {report_path}")
    if not blend_path.exists():
        raise SystemExit(f"blend missing: {blend_path}")
    if blend_path.stat().st_size < 150000:
        raise SystemExit(f"blend suspiciously small: {blend_path.stat().st_size}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("experiment") != EXPERIMENT:
        raise SystemExit("experiment id mismatch")
    if report.get("frame_end") != 144 or report.get("fps") != 24:
        raise SystemExit("unexpected timeline")

    source = report.get("source") or {}
    if source.get("publisher") != "Quaternius":
        raise SystemExit("source publisher not recorded")
    if source.get("license") != "CC0 1.0":
        raise SystemExit("expected CC0 source record")
    if source.get("asset_format") not in {".glb", ".gltf", ".fbx"}:
        raise SystemExit(f"unexpected asset format: {source.get('asset_format')}")

    char = report.get("character") or {}
    if int(char.get("mesh_count", 0)) < 1:
        raise SystemExit("no imported character mesh")
    if int(char.get("armature_count", 0)) < 1:
        raise SystemExit("no imported armature")
    if int(char.get("action_count", 0)) < 1:
        raise SystemExit("no imported animation actions")
    if int(char.get("material_count", 0)) < 1:
        raise SystemExit("no imported materials")
    height = float(char.get("preview_height", 0.0))
    if not (1.5 <= height <= 4.0):
        raise SystemExit(f"character normalization looks wrong: {height}")

    return {
        "asset_file": source.get("asset_file"),
        "asset_format": source.get("asset_format"),
        "mesh_count": char.get("mesh_count"),
        "armature_count": char.get("armature_count"),
        "action_count": char.get("action_count"),
        "selected_action": char.get("selected_action"),
        "material_count": char.get("material_count"),
        "image_count": char.get("image_count"),
        "preview_height": height,
        "blend_size_bytes": blend_path.stat().st_size,
    }


def main():
    preview = Path(sys.argv[1] if len(sys.argv) > 1 else "output/preview.png")
    base = preview.parent
    result = {
        "video": f"{EXPERIMENT}.mp4",
        "preview": validate_preview(preview),
        "movie": validate_video(base / f"{EXPERIMENT}.mp4"),
        "report": validate_report(
            base / f"{EXPERIMENT}-report.json",
            base / f"{EXPERIMENT}.blend",
        ),
    }
    out = base / "validation.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
