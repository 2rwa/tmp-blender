from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageStat


EXPECTED_NODE_TYPES = {
    "GeometryNodeMeshGrid",
    "GeometryNodeSetPosition",
    "GeometryNodeInputPosition",
    "GeometryNodeInputSceneTime",
    "ShaderNodeVectorMath",
    "ShaderNodeMath",
    "ShaderNodeCombineXYZ",
    "GeometryNodeMeshToPoints",
    "GeometryNodeMeshIcoSphere",
    "GeometryNodeSetMaterial",
    "GeometryNodeInstanceOnPoints",
    "GeometryNodeRealizeInstances",
    "NodeGroupOutput",
}


def validate_preview(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"preview missing: {path}")

    size_bytes = path.stat().st_size
    if size_bytes < 25_000:
        raise SystemExit(f"preview suspiciously small: {size_bytes} bytes")

    with Image.open(path) as image:
        image.load()
        if image.size != (768, 576):
            raise SystemExit(f"unexpected preview size: {image.size}")

        rgb = image.convert("RGB")
        gray = rgb.convert("L")
        stat = ImageStat.Stat(gray)
        extrema = gray.getextrema()
        stddev = float(stat.stddev[0])
        mean = float(stat.mean[0])
        preview = rgb.resize((64, 48))
        colors = preview.getcolors(maxcolors=3072)
        unique_colors = len(colors) if colors is not None else 3072

        if extrema[1] - extrema[0] < 50:
            raise SystemExit(f"insufficient luminance range: {extrema}")
        if stddev < 12.0:
            raise SystemExit(f"preview looks too uniform: stddev={stddev:.2f}")
        if unique_colors < 160:
            raise SystemExit(f"preview has too little visual variation: {unique_colors} colors")

    return {
        "path": str(path),
        "size_bytes": size_bytes,
        "width": 768,
        "height": 576,
        "luminance_min": extrema[0],
        "luminance_max": extrema[1],
        "luminance_mean": round(mean, 3),
        "luminance_stddev": round(stddev, 3),
        "unique_colors_64x48": unique_colors,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def validate_video(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"video missing: {path}")
    if path.stat().st_size < 80_000:
        raise SystemExit(f"video suspiciously small: {path.stat().st_size} bytes")

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,avg_frame_rate,duration,nb_frames",
            "-show_entries",
            "format=size,duration",
            "-of",
            "json",
            str(path),
        ],
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
    if width != 768 or height != 576:
        raise SystemExit(f"unexpected video size: {(width, height)}")
    if not (3.5 <= duration <= 4.5):
        raise SystemExit(f"unexpected video duration: {duration:.3f}s")

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


def validate_geometry_nodes(report_path: Path, blend_path: Path) -> dict:
    if not report_path.exists():
        raise SystemExit(f"Geometry Nodes report missing: {report_path}")
    if not blend_path.exists():
        raise SystemExit(f"blend missing: {blend_path}")
    if blend_path.stat().st_size < 100_000:
        raise SystemExit(f"blend suspiciously small: {blend_path.stat().st_size} bytes")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    node_types = set(report.get("node_types", []))
    missing = sorted(EXPECTED_NODE_TYPES - node_types)
    if missing:
        raise SystemExit(f"Geometry Nodes report missing required node types: {missing}")
    if report.get("modifier") != "GeometryNodes":
        raise SystemExit(f"unexpected modifier: {report.get('modifier')!r}")
    if report.get("grid_point_count") != 31 * 31:
        raise SystemExit(f"unexpected grid point count: {report.get('grid_point_count')}")
    if int(report.get("evaluated_vertices", 0)) < 10_000:
        raise SystemExit(f"evaluated Geometry Nodes mesh too small: {report.get('evaluated_vertices')}")
    if int(report.get("evaluated_polygons", 0)) < 20_000:
        raise SystemExit(f"evaluated Geometry Nodes polygon count too small: {report.get('evaluated_polygons')}")

    return {
        "node_group": report.get("node_group"),
        "node_count": report.get("node_count"),
        "grid_point_count": report.get("grid_point_count"),
        "frame_start": report.get("frame_start"),
        "frame_end": report.get("frame_end"),
        "fps": report.get("fps"),
        "evaluated_vertices": report.get("evaluated_vertices"),
        "evaluated_edges": report.get("evaluated_edges"),
        "evaluated_polygons": report.get("evaluated_polygons"),
        "blend_size_bytes": blend_path.stat().st_size,
    }


def main() -> None:
    preview_path = Path(sys.argv[1] if len(sys.argv) > 1 else "output/preview.png")
    base = preview_path.parent
    video_path = base / "ripple-grid.mp4"
    report_path = base / "geometry-nodes-report.json"
    blend_path = base / "geometry-nodes-movie.blend"

    result = {
        "video": video_path.name,
        "preview": validate_preview(preview_path),
        "movie": validate_video(video_path),
        "geometry_nodes": validate_geometry_nodes(report_path, blend_path),
    }
    output = base / "validation.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
