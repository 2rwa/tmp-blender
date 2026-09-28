from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import meshio
import numpy as np


CUBE_FACES = [
    [0, 1, 2], [2, 1, 3], [2, 3, 4], [4, 3, 5],
    [4, 5, 6], [6, 5, 7], [6, 7, 0], [0, 7, 1],
    [1, 7, 3], [3, 7, 5], [6, 0, 4], [4, 0, 2],
]


def frame_index(path: Path) -> int:
    match = re.search(r"_(\d+)\.vtk$", path.name)
    if not match:
        raise ValueError(f"cannot parse frame: {path}")
    return int(match.group(1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sph_output", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    vtk = args.sph_output / "vtk"
    fluid_files = sorted(vtk.glob("ParticleData_Fluid_*.vtk"), key=frame_index)
    rigid_files = sorted(vtk.glob("rb_data_1_*.vtk"), key=frame_index)
    if len(fluid_files) != 61 or len(rigid_files) != 61:
        raise SystemExit(f"expected 61/61 frames, got {len(fluid_files)}/{len(rigid_files)}")

    args.output.mkdir(parents=True, exist_ok=True)
    frames = []
    total_bytes = 0
    particle_count = None

    for sequence_frame, (fluid_path, rigid_path) in enumerate(zip(fluid_files, rigid_files), start=1):
        fluid = meshio.read(fluid_path)
        points = np.asarray(fluid.points, dtype=np.float32)
        if particle_count is None:
            particle_count = len(points)
        if len(points) != particle_count:
            raise RuntimeError(f"particle count changed at frame {sequence_frame}: {len(points)}")

        velocity = np.asarray(
            fluid.point_data.get("velocity", np.zeros_like(points)),
            dtype=np.float32,
        )
        density = np.asarray(
            fluid.point_data.get("density", np.zeros((len(points),), dtype=np.float32)),
            dtype=np.float32,
        ).reshape(-1)
        rigid = meshio.read(rigid_path)
        cube = np.asarray(rigid.points, dtype=np.float32)
        if cube.shape != (8, 3):
            raise RuntimeError(f"unexpected cube shape {cube.shape}")

        name = f"points_{sequence_frame:04d}.npz"
        path = args.output / name
        np.savez_compressed(path, points=points, velocity=velocity, density=density, cube=cube)
        total_bytes += path.stat().st_size
        frames.append({
            "sequence_frame": sequence_frame,
            "source_frame": frame_index(fluid_path),
            "file": name,
            "particles": len(points),
            "bytes": path.stat().st_size,
            "aabb_min": [float(v) for v in points.min(axis=0)],
            "aabb_max": [float(v) for v in points.max(axis=0)],
            "velocity_max": float(np.max(np.linalg.norm(velocity, axis=1))),
            "density_min": float(np.min(density)) if len(density) else 0.0,
            "density_max": float(np.max(density)) if len(density) else 0.0,
        })

    manifest = {
        "format": 1,
        "representation": "sph-points",
        "frames": len(frames),
        "fps": 12,
        "particle_count": particle_count,
        "point_npz_total_bytes": total_bytes,
        "attributes": ["position", "velocity", "density"],
        "cube_faces": CUBE_FACES,
        "frames_data": frames,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "frames": manifest["frames"],
        "particle_count": particle_count,
        "point_npz_total_bytes": total_bytes,
        "attributes": manifest["attributes"],
    }, indent=2))


if __name__ == "__main__":
    main()
