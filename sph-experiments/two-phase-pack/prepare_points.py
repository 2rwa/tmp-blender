from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import meshio
import numpy as np

PHASES = ("PhaseA", "PhaseB")

def frame_index(path: Path) -> int:
    match = re.search(r"_(\d+)\.vtk$", path.name)
    if not match:
        raise ValueError(f"cannot parse frame number: {path}")
    return int(match.group(1))

def read_phase(files: list[Path], output: Path, prefix: str):
    records = []
    particle_count = None
    total_bytes = 0
    speeds = []
    for sequence_frame, fluid_path in enumerate(files, start=1):
        fluid = meshio.read(fluid_path)
        points = np.asarray(fluid.points, dtype=np.float32)
        if particle_count is None:
            particle_count = len(points)
        if len(points) != particle_count:
            raise RuntimeError(
                f"{prefix} particle count changed at frame {sequence_frame}: "
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
        speed = np.linalg.norm(velocity, axis=1)
        speeds.append(speed)

        name = f"{prefix.lower()}_{sequence_frame:04d}.npz"
        path = output / name
        np.savez_compressed(path, points=points, velocity=velocity, density=density)
        total_bytes += path.stat().st_size
        records.append({
            "sequence_frame": sequence_frame,
            "source_frame": frame_index(fluid_path),
            "file": name,
            "particles": len(points),
            "aabb_min": [float(v) for v in points.min(axis=0)],
            "aabb_max": [float(v) for v in points.max(axis=0)],
            "centroid": [float(v) for v in points.mean(axis=0)],
            "velocity_max": float(speed.max()) if len(speed) else 0.0,
            "density_min": float(density.min()) if len(density) else 0.0,
            "density_max": float(density.max()) if len(density) else 0.0,
        })

    speed_values = np.concatenate(speeds) if speeds else np.zeros(1, dtype=np.float32)
    stats = {
        "p50": float(np.percentile(speed_values, 50)),
        "p95": float(np.percentile(speed_values, 95)),
        "p99": float(np.percentile(speed_values, 99)),
        "max": float(speed_values.max()),
    }
    return records, int(particle_count or 0), total_bytes, stats

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sph_output", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--fps", type=int, default=12)
    args = parser.parse_args()

    vtk_dir = args.sph_output / "vtk"
    phase_files = {
        phase: sorted(vtk_dir.glob(f"ParticleData_{phase}_*.vtk"), key=frame_index)
        for phase in PHASES
    }
    counts = {phase: len(files) for phase, files in phase_files.items()}
    if min(counts.values(), default=0) < 12:
        raise SystemExit(f"expected at least 12 frames per phase, got {counts}")
    if len(set(counts.values())) != 1:
        raise SystemExit(f"phase frame counts differ: {counts}")

    args.output.mkdir(parents=True, exist_ok=True)
    phase_manifest = {}
    total_bytes = 0
    for phase in PHASES:
        records, particles, bytes_used, velocity_stats = read_phase(
            phase_files[phase], args.output, phase
        )
        phase_manifest[phase] = {
            "particle_count": particles,
            "velocity_stats": velocity_stats,
            "frames_data": records,
        }
        total_bytes += bytes_used

    source_a = [r["source_frame"] for r in phase_manifest["PhaseA"]["frames_data"]]
    source_b = [r["source_frame"] for r in phase_manifest["PhaseB"]["frames_data"]]
    if source_a != source_b:
        raise SystemExit("phase source frame sequences differ")

    manifest = {
        "format": 1,
        "case": args.case,
        "representation": "two-phase-sph-points",
        "frames": counts["PhaseA"],
        "fps": args.fps,
        "phases": phase_manifest,
        "total_particle_count": sum(phase_manifest[p]["particle_count"] for p in PHASES),
        "point_npz_total_bytes": total_bytes,
        "attributes": ["position", "velocity", "density"],
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "case": args.case,
        "frames": manifest["frames"],
        "particle_counts": {p: phase_manifest[p]["particle_count"] for p in PHASES},
        "velocity_stats": {p: phase_manifest[p]["velocity_stats"] for p in PHASES},
        "point_npz_total_bytes": total_bytes,
    }, indent=2))

if __name__ == "__main__":
    main()
