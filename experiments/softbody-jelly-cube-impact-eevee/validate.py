from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageStat

EXPERIMENT = "softbody-jelly-cube-impact-eevee"


def validate_preview(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"preview missing: {path}")
    if path.stat().st_size < 10_000:
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
        if extrema[1] - extrema[0] < 70:
            raise SystemExit(f"insufficient luminance range: {extrema}")
        if stddev < 15.0:
            raise SystemExit(f"preview too uniform: {stddev:.2f}")
        if not (6.0 <= mean <= 210.0):
            raise SystemExit(f"unexpected luminance mean: {mean:.2f}")

    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "width": 480,
        "height": 360,
        "luminance_min": extrema[0],
        "luminance_max": extrema[1],
        "luminance_mean": round(mean, 3),
        "luminance_stddev": round(stddev, 3),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def validate_video(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"video missing: {path}")
    if path.stat().st_size < 35_000:
        raise SystemExit(f"video suspiciously small: {path.stat().st_size}")

    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,avg_frame_rate,duration,nb_frames",
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
    duration = float(stream.get("duration") or fmt.get("duration") or 0.0)

    if (width, height) != (480, 360):
        raise SystemExit(f"unexpected video size: {(width, height)}")
    if not (5.5 <= duration <= 6.5):
        raise SystemExit(f"unexpected video duration: {duration:.3f}")

    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "width": width,
        "height": height,
        "duration_seconds": round(duration, 3),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "nb_frames": stream.get("nb_frames"),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def validate_report(report_path: Path, blend_path: Path) -> dict:
    if not report_path.exists():
        raise SystemExit(f"report missing: {report_path}")
    if not blend_path.exists():
        raise SystemExit(f"blend missing: {blend_path}")
    if blend_path.stat().st_size < 300_000:
        raise SystemExit(f"blend suspiciously small: {blend_path.stat().st_size}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    expected = {
        "experiment": EXPERIMENT,
        "frame_start": 1,
        "frame_end": 144,
        "fps": 24,
        "resolution_x": 480,
        "resolution_y": 360,
    }
    for key, value in expected.items():
        if report.get(key) != value:
            raise SystemExit(f"unexpected {key}: {report.get(key)}")

    jelly = report.get("jelly") or {}
    if int(jelly.get("vertex_count", 0)) < 150:
        raise SystemExit(f"jelly mesh too small: {jelly.get('vertex_count')}")
    if int(jelly.get("face_count", 0)) < 120:
        raise SystemExit(f"jelly face count too small: {jelly.get('face_count')}")
    if int(jelly.get("baked_shape_keys", 0)) != 144:
        raise SystemExit(f"unexpected baked frames: {jelly.get('baked_shape_keys')}")
    if int(jelly.get("shape_key_count", 0)) < 145:
        raise SystemExit(f"shape keys missing: {jelly.get('shape_key_count')}")

    max_displacement = float(jelly.get("max_displacement", 0.0))
    if max_displacement < 0.08:
        raise SystemExit(f"jelly did not visibly deform: max displacement={max_displacement:.6f}")

    impact_frame = int(jelly.get("max_displacement_frame", 0))
    if not (20 <= impact_frame <= 144):
        raise SystemExit(f"unexpected max displacement frame: {impact_frame}")

    projectile = report.get("projectile") or {}
    if projectile.get("name") != "ImpactSphere":
        raise SystemExit(f"projectile missing: {projectile.get('name')}")
    if int(projectile.get("keyframes", 0)) < 6:
        raise SystemExit(f"projectile animation too sparse: {projectile.get('keyframes')}")
    if len(projectile.get("path") or []) < 6:
        raise SystemExit("projectile path missing")

    return {
        "engine": report.get("engine"),
        "vertex_count": jelly.get("vertex_count"),
        "face_count": jelly.get("face_count"),
        "baked_shape_keys": jelly.get("baked_shape_keys"),
        "shape_key_count": jelly.get("shape_key_count"),
        "simulation_seconds": jelly.get("simulation_seconds"),
        "max_displacement": jelly.get("max_displacement"),
        "max_displacement_frame": jelly.get("max_displacement_frame"),
        "projectile_keyframes": projectile.get("keyframes"),
        "blend_size_bytes": blend_path.stat().st_size,
    }


def main() -> None:
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
