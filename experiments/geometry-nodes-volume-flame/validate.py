from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageStat


EXPECTED_NODE_TYPES = {
    "NodeGroupInput",
    "GeometryNodeInputPosition",
    "GeometryNodeInputIndex",
    "GeometryNodeInputSceneTime",
    "ShaderNodeSeparateXYZ",
    "ShaderNodeCombineXYZ",
    "ShaderNodeMath",
    "GeometryNodeSetPosition",
    "GeometryNodeMeshToPoints",
    "GeometryNodePointsToVolume",
    "GeometryNodeSetMaterial",
    "NodeGroupOutput",
}


def validate_preview(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"preview missing: {path}")
    size_bytes = path.stat().st_size
    if size_bytes < 8_000:
        raise SystemExit(f"preview suspiciously small: {size_bytes} bytes")

    with Image.open(path) as image:
        image.load()
        if image.size != (480, 360):
            raise SystemExit(f"unexpected preview size: {image.size}")
        rgb = image.convert("RGB")
        gray = rgb.convert("L")
        stat = ImageStat.Stat(gray)
        extrema = gray.getextrema()
        stddev = float(stat.stddev[0])
        mean = float(stat.mean[0])
        sample = rgb.resize((64, 48))
        colors = sample.getcolors(maxcolors=3072)
        unique_colors = len(colors) if colors is not None else 3072
        if extrema[1] - extrema[0] < 35:
            raise SystemExit(f"insufficient luminance range: {extrema}")
        if stddev < 8.0:
            raise SystemExit(f"preview looks too uniform: stddev={stddev:.2f}")
        if unique_colors < 80:
            raise SystemExit(f"preview has too little visual variation: {unique_colors} colors")

    return {
        "path": str(path),
        "size_bytes": size_bytes,
        "width": 480,
        "height": 360,
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
    if path.stat().st_size < 20_000:
        raise SystemExit(f"video suspiciously small: {path.stat().st_size} bytes")

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,avg_frame_rate,duration,nb_frames",
            "-show_entries", "format=size,duration", "-of", "json", str(path),
        ],
        check=True, capture_output=True, text=True,
    )
    data = json.loads(probe.stdout)
    stream = (data.get("streams") or [{}])[0]
    fmt = data.get("format") or {}
    width = int(stream.get("width", 0))
    height = int(stream.get("height", 0))
    duration = float(stream.get("duration") or fmt.get("duration") or 0.0)
    if width != 480 or height != 360:
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
    if int(report.get("seed_point_count", 0)) < 300:
        raise SystemExit(f"too few seed points: {report.get('seed_point_count')}")
    if report.get("points_to_volume_resolution_mode") != "VOXEL_SIZE":
        raise SystemExit("Points to Volume is not using VOXEL_SIZE")
    voxel_size = float(report.get("points_to_volume_voxel_size", 99.0))
    if not (0.05 <= voxel_size <= 0.15):
        raise SystemExit(f"unexpected voxel size: {voxel_size}")
    if "ShaderNodeVolumePrincipled" not in set(report.get("material_node_types", [])):
        raise SystemExit("Principled Volume material node missing")
    if report.get("resolution_x") != 480 or report.get("resolution_y") != 360:
        raise SystemExit("unexpected pre-render resolution")

    return {
        "node_group": report.get("node_group"),
        "node_count": report.get("node_count"),
        "seed_point_count": report.get("seed_point_count"),
        "voxel_size": voxel_size,
        "frame_start": report.get("frame_start"),
        "frame_end": report.get("frame_end"),
        "fps": report.get("fps"),
        "material_inputs_applied": report.get("material_inputs_applied"),
        "blend_size_bytes": blend_path.stat().st_size,
    }


def main() -> None:
    preview_path = Path(sys.argv[1] if len(sys.argv) > 1 else "output/preview.png")
    base = preview_path.parent
    video_path = base / "volume-flame.mp4"
    report_path = base / "geometry-nodes-volume-flame-report.json"
    blend_path = base / "geometry-nodes-volume-flame.blend"
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
