from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import meshio
import numpy as np


FPS = 12
SPARSE_STRIDE = 8
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

    raw_frames: list[dict[str, object]] = []
    particle_count: int | None = None

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

        raw_frames.append({
            "sequence_frame": sequence_frame,
            "source_frame": frame_index(fluid_path),
            "points": points,
            "velocity": velocity,
            "density": density,
            "cube": cube,
        })

    assert particle_count is not None
    dt = 1.0 / FPS
    all_speeds = np.concatenate([
        np.linalg.norm(np.asarray(f["velocity"]), axis=1)
        for f in raw_frames
    ])
    speed_p95 = float(np.percentile(all_speeds, 95.0))
    speed_p99 = float(np.percentile(all_speeds, 99.0))

    accelerations: list[np.ndarray] = []
    for i, frame in enumerate(raw_frames):
        vel = np.asarray(frame["velocity"], dtype=np.float32)
        if i == 0:
            acc = np.zeros_like(vel)
        else:
            prev = np.asarray(raw_frames[i - 1]["velocity"], dtype=np.float32)
            acc = (vel - prev) / dt
        accelerations.append(acc.astype(np.float32))

    if len(accelerations) > 1:
        accelerations[0] = accelerations[1].copy()

    all_accel_mag = np.concatenate([np.linalg.norm(a, axis=1) for a in accelerations])
    accel_percentiles = {
        str(p): float(np.percentile(all_accel_mag, p))
        for p in (50, 75, 90, 95, 97, 99)
    }
    accel_scale = max(accel_percentiles["97"], 1.0e-6)

    args.output.mkdir(parents=True, exist_ok=True)
    frames = []
    total_bytes = 0
    sparse_count = (particle_count + SPARSE_STRIDE - 1) // SPARSE_STRIDE

    for frame, acceleration in zip(raw_frames, accelerations):
        sequence_frame = int(frame["sequence_frame"])
        points = np.asarray(frame["points"], dtype=np.float32)
        velocity = np.asarray(frame["velocity"], dtype=np.float32)
        density = np.asarray(frame["density"], dtype=np.float32)
        cube = np.asarray(frame["cube"], dtype=np.float32)
        accel_mag = np.linalg.norm(acceleration, axis=1).astype(np.float32)
        accel_norm = np.clip(accel_mag / accel_scale, 0.0, 1.0).astype(np.float32)

        name = f"points_{sequence_frame:04d}.npz"
        path = args.output / name
        np.savez_compressed(
            path,
            points=points,
            velocity=velocity,
            density=density,
            acceleration=acceleration,
            acceleration_magnitude=accel_mag,
            acceleration_normalized=accel_norm,
            cube=cube,
        )
        total_bytes += path.stat().st_size
        speeds = np.linalg.norm(velocity, axis=1)
        frames.append({
            "sequence_frame": sequence_frame,
            "source_frame": int(frame["source_frame"]),
            "file": name,
            "particles": len(points),
            "bytes": path.stat().st_size,
            "aabb_min": [float(v) for v in points.min(axis=0)],
            "aabb_max": [float(v) for v in points.max(axis=0)],
            "velocity_max": float(np.max(speeds)),
            "velocity_mean": float(np.mean(speeds)),
            "acceleration_max": float(np.max(accel_mag)),
            "acceleration_mean": float(np.mean(accel_mag)),
            "density_min": float(np.min(density)) if len(density) else 0.0,
            "density_max": float(np.max(density)) if len(density) else 0.0,
        })

    manifest = {
        "format": 2,
        "representation": "sph-point-diagnostics",
        "frames": len(frames),
        "fps": FPS,
        "particle_count": particle_count,
        "sparse_stride": SPARSE_STRIDE,
        "sparse_particle_count": sparse_count,
        "point_npz_total_bytes": total_bytes,
        "attributes": [
            "position",
            "velocity",
            "density",
            "acceleration",
            "acceleration_magnitude",
            "acceleration_normalized",
        ],
        "velocity_stats": {
            "p95": speed_p95,
            "p99": speed_p99,
        },
        "acceleration_stats": {
            "normalization_percentile": 97,
            "normalization_value": accel_scale,
            "percentiles": accel_percentiles,
        },
        "cube_faces": CUBE_FACES,
        "frames_data": frames,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "frames": manifest["frames"],
        "particle_count": particle_count,
        "sparse_particle_count": sparse_count,
        "point_npz_total_bytes": total_bytes,
        "velocity_stats": manifest["velocity_stats"],
        "acceleration_stats": manifest["acceleration_stats"],
    }, indent=2))


if __name__ == "__main__":
    main()
