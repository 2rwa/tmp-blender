from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageStat

EXPECTED_NODE_TYPES = {
    "GeometryNodeMeshToPoints",
    "GeometryNodeSetPosition",
    "GeometryNodePointsToVolume",
    "GeometryNodeSetMaterial",
    "GeometryNodeInputPosition",
    "GeometryNodeInputIndex",
    "GeometryNodeInputSceneTime",
    "ShaderNodeSeparateXYZ",
    "ShaderNodeCombineXYZ",
    "ShaderNodeMath",
    "NodeGroupInput",
    "NodeGroupOutput",
}


def validate_preview(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"preview missing: {path}")
    with Image.open(path) as image:
        image.load()
        if image.size != (480, 360):
            raise SystemExit(f"unexpected preview size: {image.size}")
        rgb = image.convert("RGB")
        gray = rgb.convert("L")
        stat = ImageStat.Stat(gray)
        extrema = gray.getextrema()
        mean = float(stat.mean[0])
        stddev = float(stat.stddev[0])
        small = rgb.resize((120, 90))
        pixels = list(small.getdata())
        warm = sum(1 for r, g, b in pixels if r >= 80 and r > g > b and (r - b) >= 40)
        white = sum(1 for r, g, b in pixels if r >= 245 and g >= 235 and b >= 220)
        total = len(pixels)
        if (extrema[1] - extrema[0]) < 70:
            raise SystemExit(f"insufficient luminance range: {extrema}")
        if stddev < 14.0:
            raise SystemExit(f"preview looks too uniform: stddev={stddev:.2f}")
        if not (5.0 <= mean <= 160.0):
            raise SystemExit(f"unexpected luminance mean: {mean:.2f}")
        if warm / total < 0.005:
            raise SystemExit("warm flame colors too scarce")
        if white / total > 0.08:
            raise SystemExit("white-hot blowout too large")
    return {
        "path": str(path),
        "width": 480,
        "height": 360,
        "luminance_min": extrema[0],
        "luminance_max": extrema[1],
        "luminance_mean": round(mean, 3),
        "luminance_stddev": round(stddev, 3),
        "warm_ratio": round(warm / total, 5),
        "white_ratio": round(white / total, 5),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def validate_video(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"video missing: {path}")
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,avg_frame_rate,duration,nb_frames", "-show_entries", "format=size,duration", "-of", "json", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(probe.stdout)
    stream = (data.get("streams") or [{}])[0]
    fmt = data.get("format") or {}
    width = int(stream.get("width", 0))
    height = int(stream.get("height", 0))
    duration = float(stream.get("duration") or fmt.get("duration") or 0.0)
    if (width, height) != (480, 360):
        raise SystemExit(f"unexpected video size: {(width, height)}")
    if not (3.5 <= duration <= 4.5):
        raise SystemExit(f"unexpected video duration: {duration:.3f}s")
    return {
        "path": str(path),
        "width": width,
        "height": height,
        "duration_seconds": round(duration, 3),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "nb_frames": stream.get("nb_frames"),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def validate_report(report_path: Path, blend_path: Path) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("resolution_x") != 480 or report.get("resolution_y") != 360:
        raise SystemExit("unexpected pre-render resolution")
    if report.get("frame_start") != 1 or report.get("frame_end") != 96:
        raise SystemExit("unexpected frame range")
    groups = report.get("groups") or []
    if len(groups) != 2:
        raise SystemExit(f"expected 2 flame groups, got {len(groups)}")
    node_types = set()
    seed_counts = []
    for group in groups:
        node_types.update(group.get("node_types", []))
        seed_counts.append(int(group.get("seed_point_count", 0)))
    missing = sorted(EXPECTED_NODE_TYPES - node_types)
    if missing:
        raise SystemExit(f"missing Geometry Nodes types: {missing}")
    if seed_counts != [520, 180]:
        raise SystemExit(f"unexpected seed counts: {seed_counts}")
    outer = (report.get("materials") or {}).get("outer") or {}
    core = (report.get("materials") or {}).get("core") or {}
    if float(outer.get("emission_strength", 0.0)) > 1.4:
        raise SystemExit("outer flame emission strength too high")
    if float(core.get("emission_strength", 0.0)) > 2.2:
        raise SystemExit("core flame emission strength too high")
    return {
        "frame_start": report.get("frame_start"),
        "frame_end": report.get("frame_end"),
        "fps": report.get("fps"),
        "resolution_x": report.get("resolution_x"),
        "resolution_y": report.get("resolution_y"),
        "requested_render_samples": report.get("requested_render_samples"),
        "effective_render_samples": report.get("effective_render_samples"),
        "seed_counts": seed_counts,
        "blend_size_bytes": blend_path.stat().st_size,
        "materials": report.get("materials"),
    }


def main() -> None:
    preview_path = Path(sys.argv[1] if len(sys.argv) > 1 else "output/preview.png")
    base = preview_path.parent
    result = {
        "video": "volume-flame-v2.mp4",
        "preview": validate_preview(preview_path),
        "movie": validate_video(base / "volume-flame-v2.mp4"),
        "report": validate_report(base / "geometry-nodes-volume-flame-v2-report.json", base / "geometry-nodes-volume-flame-v2.blend"),
    }
    (base / "validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
