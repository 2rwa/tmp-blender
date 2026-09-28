from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import meshio
import numpy as np

def frame_index(path: Path) -> int:
    m = re.search(r"_(\d+)\.vtk$", path.name)
    if not m:
        raise ValueError(f"cannot parse frame number: {path}")
    return int(m.group(1))

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sph_output", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--fps", type=int, default=12)
    args = parser.parse_args()

    vtk_dir = args.sph_output / "vtk"
    files = sorted(vtk_dir.glob("ParticleData_Fluid_*.vtk"), key=frame_index)
    if len(files) < 12:
        raise SystemExit(f"expected at least 12 frames, got {len(files)}")

    args.output.mkdir(parents=True, exist_ok=True)
    particle_count = None
    total_bytes = 0
    frames = []
    speeds_all = []
    initial_extent = None

    for sequence_frame, source in enumerate(files, start=1):
        mesh = meshio.read(source)
        points = np.asarray(mesh.points, dtype=np.float32)
        if particle_count is None:
            particle_count = len(points)
        if len(points) != particle_count:
            raise RuntimeError(f"particle count changed: {len(points)} != {particle_count}")

        velocity = np.asarray(mesh.point_data.get("velocity", np.zeros_like(points)), dtype=np.float32)
        density = np.asarray(
            mesh.point_data.get("density", np.zeros((len(points),), dtype=np.float32)),
            dtype=np.float32,
        ).reshape(-1)
        speed = np.linalg.norm(velocity, axis=1)
        speeds_all.append(speed)

        aabb_min = points.min(axis=0)
        aabb_max = points.max(axis=0)
        extent = aabb_max - aabb_min
        if initial_extent is None:
            initial_extent = extent.copy()

        out_name = f"points_{sequence_frame:04d}.npz"
        out = args.output / out_name
        np.savez_compressed(out, points=points, velocity=velocity, density=density)
        total_bytes += out.stat().st_size

        frames.append({
            "sequence_frame": sequence_frame,
            "source_frame": frame_index(source),
            "file": out_name,
            "particles": len(points),
            "centroid": [float(v) for v in points.mean(axis=0)],
            "aabb_min": [float(v) for v in aabb_min],
            "aabb_max": [float(v) for v in aabb_max],
            "extent": [float(v) for v in extent],
            "extent_ratio": [
                float(extent[i] / initial_extent[i]) if initial_extent[i] > 1e-8 else 1.0
                for i in range(3)
            ],
            "velocity_max": float(speed.max()) if len(speed) else 0.0,
        })

    speeds = np.concatenate(speeds_all)
    manifest = {
        "format": 1,
        "case": args.case,
        "representation": "elastic-sph-points",
        "frames": len(frames),
        "fps": args.fps,
        "particle_count": particle_count,
        "point_npz_total_bytes": total_bytes,
        "velocity_stats": {
            "p50": float(np.percentile(speeds, 50)),
            "p95": float(np.percentile(speeds, 95)),
            "p99": float(np.percentile(speeds, 99)),
            "max": float(speeds.max())
        },
        "frames_data": frames
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "case": args.case,
        "frames": len(frames),
        "particle_count": particle_count,
        "velocity_stats": manifest["velocity_stats"],
        "final_extent_ratio": frames[-1]["extent_ratio"]
    }, indent=2))

if __name__ == "__main__":
    main()
