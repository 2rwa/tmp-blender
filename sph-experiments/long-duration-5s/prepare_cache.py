from __future__ import annotations

import argparse
import json
import math
import re
import time
from pathlib import Path

import meshio
import numpy as np
import pysplashsurf


PARTICLE_RADIUS = 0.05
SMOOTHING_LENGTH = 0.10
CUBE_SIZE = 0.05
THRESHOLDS = (0.6, 0.5, 0.4, 0.3)
CUBE_FACES = [
    [0, 1, 2], [2, 1, 3], [2, 3, 4], [4, 3, 5],
    [4, 5, 6], [6, 5, 7], [6, 7, 0], [0, 7, 1],
    [1, 7, 3], [3, 7, 5], [6, 0, 4], [4, 0, 2],
]


def frame_index(path: Path) -> int:
    match = re.search(r"_(\d+)\.vtk$", path.name)
    if not match:
        raise ValueError(f"cannot parse frame index: {path}")
    return int(match.group(1))


def centroid(points: np.ndarray) -> list[float]:
    return [float(v) for v in np.mean(points, axis=0)]


def reconstruct(points: np.ndarray):
    attempts = []
    for threshold in THRESHOLDS:
        result = pysplashsurf.reconstruct_surface(
            points,
            particle_radius=PARTICLE_RADIUS,
            rest_density=1000.0,
            smoothing_length=SMOOTHING_LENGTH,
            cube_size=CUBE_SIZE,
            iso_surface_threshold=threshold,
            subdomain_grid=False,
        )
        mesh = result.mesh
        vertices = np.asarray(mesh.vertices, dtype=np.float32)
        triangles = np.asarray(mesh.triangles, dtype=np.int32)
        attempts.append(
            {
                "threshold": threshold,
                "vertices": int(len(vertices)),
                "faces": int(len(triangles)),
            }
        )
        if len(vertices) and len(triangles):
            return threshold, vertices, triangles, attempts
    raise RuntimeError(f"empty reconstruction: {attempts}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sph_output", type=Path)
    parser.add_argument("cache_output", type=Path)
    args = parser.parse_args()

    vtk_dir = args.sph_output / "vtk"
    particle_files = sorted(vtk_dir.glob("ParticleData_Fluid_*.vtk"), key=frame_index)
    rigid_files = sorted(vtk_dir.glob("rb_data_1_*.vtk"), key=frame_index)
    if not particle_files or not rigid_files:
        raise SystemExit("missing fluid or rigid-body VTK frames")

    particle_ids = [frame_index(p) for p in particle_files]
    rigid_ids = [frame_index(p) for p in rigid_files]
    if particle_ids != rigid_ids:
        raise SystemExit(
            f"fluid/rigid frame mismatch: fluid={particle_ids} rigid={rigid_ids}"
        )
    if len(particle_files) < 55:
        raise SystemExit(f"expected long run with >=55 frames, got {len(particle_files)}")

    surface_dir = args.cache_output / "surfaces"
    surface_dir.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    surface_records = []
    rigid_records = []
    total_npz_bytes = 0

    for sequence_frame, (particle_path, rigid_path) in enumerate(
        zip(particle_files, rigid_files),
        start=1,
    ):
        source_frame = frame_index(particle_path)
        fluid = meshio.read(particle_path)
        points = np.asarray(fluid.points, dtype=np.float64)
        if len(points) < 100:
            raise RuntimeError(f"frame {source_frame}: only {len(points)} particles")

        t0 = time.perf_counter()
        threshold, vertices, triangles, attempts = reconstruct(points)
        reconstruction_seconds = time.perf_counter() - t0

        npz_name = f"surface_{sequence_frame:04d}.npz"
        npz_path = surface_dir / npz_name
        np.savez_compressed(npz_path, vertices=vertices, triangles=triangles)
        total_npz_bytes += npz_path.stat().st_size

        rigid = meshio.read(rigid_path)
        rigid_points = np.asarray(rigid.points, dtype=np.float32)
        if rigid_points.shape != (8, 3):
            raise RuntimeError(
                f"frame {source_frame}: expected rigid points (8,3), got {rigid_points.shape}"
            )

        surface_records.append(
            {
                "sequence_frame": sequence_frame,
                "source_frame": source_frame,
                "particle_count": int(len(points)),
                "npz": npz_name,
                "threshold": threshold,
                "vertices": int(len(vertices)),
                "faces": int(len(triangles)),
                "npz_bytes": npz_path.stat().st_size,
                "reconstruction_seconds": reconstruction_seconds,
                "attempts": attempts,
            }
        )
        rigid_records.append(
            {
                "sequence_frame": sequence_frame,
                "source_frame": source_frame,
                "points": rigid_points.tolist(),
                "centroid": centroid(rigid_points),
            }
        )
        print(
            f"LONG_RECON frame={sequence_frame}/{len(particle_files)} "
            f"source={source_frame} particles={len(points)} "
            f"vertices={len(vertices)} faces={len(triangles)} "
            f"seconds={reconstruction_seconds:.3f}"
        )

    elapsed = time.perf_counter() - start
    centroids = np.asarray([r["centroid"] for r in rigid_records], dtype=np.float64)
    steps = np.linalg.norm(np.diff(centroids, axis=0), axis=1)
    dx = np.diff(centroids[:, 0])
    reversals = int(
        np.sum(
            (np.sign(dx[:-1]) != 0)
            & (np.sign(dx[1:]) != 0)
            & (np.sign(dx[:-1]) != np.sign(dx[1:]))
        )
    )

    manifest = {
        "format": 1,
        "fps": 12,
        "duration_requested_seconds": 5.0,
        "frames": len(surface_records),
        "particle_radius": PARTICLE_RADIUS,
        "smoothing_length": SMOOTHING_LENGTH,
        "cube_size": CUBE_SIZE,
        "surface_frames": surface_records,
        "rigid_body": {
            "faces": CUBE_FACES,
            "frames": rigid_records,
            "path_length_m": float(np.sum(steps)),
            "first_centroid": rigid_records[0]["centroid"],
            "last_centroid": rigid_records[-1]["centroid"],
            "centroid_min": [float(v) for v in np.min(centroids, axis=0)],
            "centroid_max": [float(v) for v in np.max(centroids, axis=0)],
            "x_direction_reversals": reversals,
        },
        "surface_npz_total_bytes": total_npz_bytes,
        "reconstruction_total_seconds": elapsed,
    }
    path = args.cache_output / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "frames": manifest["frames"],
        "surface_npz_total_bytes": total_npz_bytes,
        "reconstruction_total_seconds": elapsed,
        "rigid_path_length_m": manifest["rigid_body"]["path_length_m"],
        "rigid_centroid_min": manifest["rigid_body"]["centroid_min"],
        "rigid_centroid_max": manifest["rigid_body"]["centroid_max"],
        "x_direction_reversals": reversals,
    }, indent=2))


if __name__ == "__main__":
    main()
