from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageStat

EXPERIMENT = "metaball-hidden-funnel-300-eevee"


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
        if extrema[1] - extrema[0] < 55:
            raise SystemExit(f"insufficient luminance range: {extrema}")
        if stddev < 10.0:
            raise SystemExit(f"preview too uniform: {stddev:.2f}")
        if not (4.0 <= mean <= 220.0):
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
    if path.stat().st_size < 15_000:
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
    if blend_path.stat().st_size < 300_000:
        raise SystemExit(f"blend suspiciously small: {blend_path.stat().st_size}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    expected = {
        "experiment": EXPERIMENT,
        "frame_start": 1,
        "frame_end": 192,
        "fps": 24,
        "resolution_x": 480,
        "resolution_y": 360,
    }
    for key, value in expected.items():
        if report.get(key) != value:
            raise SystemExit(f"unexpected {key}: {report.get(key)}")

    meta = report.get("metaball") or {}
    if int(meta.get("element_count", 0)) != 300:
        raise SystemExit(f"unexpected metaball count: {meta.get('element_count')}")
    if int(meta.get("keyframe_points", 0)) < 100_000:
        raise SystemExit(f"too few metaball keyframes: {meta.get('keyframe_points')}")

    physics = report.get("physics") or {}
    if int(physics.get("proxy_count", 0)) != 300:
        raise SystemExit(f"unexpected proxy count: {physics.get('proxy_count')}")
    if not physics.get("hidden_funnel") or not physics.get("hidden_tube"):
        raise SystemExit("hidden funnel/tube metadata missing")

    # This is an experiment: do not demand perfection, but require enough actual
    # Bullet traffic through the invisible pipe to prove collision routing happened.
    exited = int(physics.get("exited_count", 0))
    in_dish = int(physics.get("in_dish_final", 0))
    leaked = int(physics.get("leaked_below_world", 0))
    if exited < 30:
        raise SystemExit(f"too few proxies exited hidden tube: {exited}")
    if in_dish < 20:
        raise SystemExit(f"too few proxies reached receiver: {in_dish}")
    if leaked > 180:
        raise SystemExit(f"too many proxies leaked below world: {leaked}")

    seconds = float(physics.get("simulation_seconds", 0.0))
    if not (0.01 <= seconds <= 3600.0):
        raise SystemExit(f"unexpected simulation time: {seconds}")

    return {
        "engine": report.get("engine"),
        "element_count": meta.get("element_count"),
        "keyframe_points": meta.get("keyframe_points"),
        "simulation_seconds": physics.get("simulation_seconds"),
        "exited_count": exited,
        "first_exit_frame": physics.get("first_exit_frame"),
        "last_exit_frame": physics.get("last_exit_frame"),
        "in_dish_final": in_dish,
        "leaked_below_world": leaked,
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
