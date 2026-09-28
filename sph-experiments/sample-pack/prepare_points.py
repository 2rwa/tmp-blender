from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import meshio
import numpy as np


def frame_index(path: Path) -> int:
    match = re.search(r"_(\d+)\.vtk$", path.name)
    if not match:
        raise ValueError(f"cannot parse frame number: {path}")
    return int(match.group(1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sph_output", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--fps", type=int, default=12)
    args = parser.parse_args()

    vtk_dir = args.sph_output / "vtk"
    fluid_files = sorted(vtk_dir.glob("ParticleData_Fluid_*.vtk"), key=frame_index)
    if len(fluid_files) < 12:
        raise SystemExit(f"expected at least 12 particle frames, got {len(fluid_files)}")

    args.output.mkdir(parents=True, exist_ok=True)
    frames = []
    particle_count = None
    total_bytes = 0
    all_speeds = []

    for sequence_frame, fluid_path in enumerate(fluid_files, start=1):
        fluid = meshio.read(fluid_path)
        points = np.asarray(fluid.points, dtype=np.float32)
        if particle_count is None:
            particle_count = len(points)
        if len(points) != particle_count:
            raise RuntimeError(
                f"particle count changed at frame {sequence_frame}: "
                f"{len(points)} != {particle_count}"
            )

        velocity = np.asarray(
            fluid.point_data.get("velocity", np.zeros_like(points)),
            dtype=np.float32,
        )
        density = np.asarray(
            fluid.point_data.get("density", np.zeros((len(points),), dtype=np.float32)),
            dtype=np.float32,
        ).reshape(-1)

        speeds = np.linalg.norm(velocity, axis=1)
        all_speeds.append(speeds)

        name = f"points_{sequence_frame:04d}.npz"
        path = args.output / name
        np.savez_compressed(path, points=points, velocity=velocity, density=density)
        total_bytes += path.stat().st_size
        frames.append({
            "sequence_frame": sequence_frame,
            "source_frame": frame_index(fluid_path),
            "file": name,
            "particles": len(points),
            "aabb_min": [float(v) for v in points.min(axis=0)],
            "aabb_max": [float(v) for v in points.max(axis=0)],
            "velocity_max": float(speeds.max()) if len(speeds) else 0.0,
            "density_min": float(density.min()) if len(density) else 0.0,
            "density_max": float(density.max()) if len(density) else 0.0,
        })

    speed_values = np.concatenate(all_speeds) if all_speeds else np.zeros(1, dtype=np.float32)
    manifest = {
        "format": 1,
        "case": args.case,
        "representation": "sph-points",
        "frames": len(frames),
        "fps": args.fps,
        "particle_count": particle_count,
        "point_npz_total_bytes": total_bytes,
        "attributes": ["position", "velocity", "density"],
        "velocity_stats": {
            "p50": float(np.percentile(speed_values, 50)),
            "p95": float(np.percentile(speed_values, 95)),
            "p99": float(np.percentile(speed_values, 99)),
            "max": float(speed_values.max()),
        },
        "frames_data": frames,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "case": args.case,
        "frames": manifest["frames"],
        "particle_count": particle_count,
        "velocity_stats": manifest["velocity_stats"],
        "point_npz_total_bytes": total_bytes,
    }, indent=2))


if __name__ == "__main__":
    main()
