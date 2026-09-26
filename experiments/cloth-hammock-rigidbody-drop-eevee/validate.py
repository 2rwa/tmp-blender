from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageStat


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
        if extrema[1] - extrema[0] < 80:
            raise SystemExit(f"insufficient luminance range: {extrema}")
        if stddev < 18.0:
            raise SystemExit(f"preview too uniform: {stddev:.2f}")
        if not (8.0 <= mean <= 205.0):
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
    if path.stat().st_size < 40_000:
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
    if not (7.5 <= duration <= 8.5):
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
    if blend_path.stat().st_size < 500_000:
        raise SystemExit(f"blend suspiciously small: {blend_path.stat().st_size}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    cloth = report.get("cloth") or {}

    expected = {
        "frame_start": 1,
        "frame_end": 192,
        "resolution_x": 480,
        "resolution_y": 360,
    }
    for key, value in expected.items():
        if report.get(key) != value:
            raise SystemExit(f"unexpected {key}: {report.get(key)}")

    if int(cloth.get("vertex_count", 0)) < 1400:
        raise SystemExit(f"cloth mesh too small: {cloth.get('vertex_count')}")
    if int(cloth.get("pinned_vertex_count", 0)) < 20:
        raise SystemExit(f"too few pinned vertices: {cloth.get('pinned_vertex_count')}")
    if cloth.get("self_collision") is not True:
        raise SystemExit("self collision disabled")
    if int(cloth.get("baked_shape_keys", 0)) != 192:
        raise SystemExit(f"unexpected baked frames: {cloth.get('baked_shape_keys')}")
    if int(cloth.get("shape_key_count", 0)) < 193:
        raise SystemExit(f"shape keys missing: {cloth.get('shape_key_count')}")
    rigid = report.get("rigid_bodies") or {}
    if int(rigid.get("count", 0)) != 12:
        raise SystemExit(f"unexpected rigid body count: {rigid.get('count')}")
    if len(rigid.get("names") or []) != 12:
        raise SystemExit("rigid body names missing")
    if not rigid.get("proxy"):
        raise SystemExit("rigid-body coupling proxy missing")
    if len(report.get("effectors") or []) != 2:
        raise SystemExit(f"unexpected effector count: {report.get('effectors')}")

    return {
        "engine": report.get("engine"),
        "vertex_count": cloth.get("vertex_count"),
        "face_count": cloth.get("face_count"),
        "pinned_vertex_count": cloth.get("pinned_vertex_count"),
        "baked_shape_keys": cloth.get("baked_shape_keys"),
        "shape_key_count": cloth.get("shape_key_count"),
        "simulation_seconds": cloth.get("simulation_seconds"),
        "rigid_body_count": rigid.get("count"),
        "rigid_body_bake_seconds": rigid.get("bake_seconds"),
        "rigid_body_proxy": rigid.get("proxy"),
        "effectors": report.get("effectors"),
        "blend_size_bytes": blend_path.stat().st_size,
    }


def main() -> None:
    preview = Path(sys.argv[1] if len(sys.argv) > 1 else "output/preview.png")
    base = preview.parent
    result = {
        "video": "cloth-hammock-rigidbody-drop-eevee.mp4",
        "preview": validate_preview(preview),
        "movie": validate_video(base / "cloth-hammock-rigidbody-drop-eevee.mp4"),
        "report": validate_report(
            base / "cloth-hammock-rigidbody-drop-eevee-report.json",
            base / "cloth-hammock-rigidbody-drop-eevee.blend",
        ),
    }
    out = base / "validation.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
