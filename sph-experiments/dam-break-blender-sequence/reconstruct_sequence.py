from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import meshio
import numpy as np
import pysplashsurf


PARTICLE_RADIUS = 0.05
SMOOTHING_LENGTH = 2.0 * PARTICLE_RADIUS
CUBE_SIZE = 1.0 * PARTICLE_RADIUS
THRESHOLDS = (0.6, 0.5, 0.4, 0.3)


def frame_index(path: Path) -> int:
    match = re.search(r"_(\d+)\.vtk$", path.name)
    if not match:
        raise ValueError(f"cannot parse frame index from {path.name}")
    return int(match.group(1))


def reconstruct_one(particles: np.ndarray):
    diagnostics = []
    for threshold in THRESHOLDS:
        reconstruction = pysplashsurf.reconstruct_surface(
            particles,
            particle_radius=PARTICLE_RADIUS,
            rest_density=1000.0,
            smoothing_length=SMOOTHING_LENGTH,
            cube_size=CUBE_SIZE,
            iso_surface_threshold=threshold,
            subdomain_grid=False,
        )
        mesh = reconstruction.mesh
        nv = len(mesh.vertices)
        nt = len(mesh.triangles)
        diagnostics.append((threshold, nv, nt))
        if nv > 0 and nt > 0:
            return threshold, mesh, diagnostics
    return None, None, diagnostics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sph_output", type=Path)
    parser.add_argument("sequence_output", type=Path)
    args = parser.parse_args()

    vtk_dir = args.sph_output / "vtk"
    particle_files = sorted(
        vtk_dir.glob("ParticleData_Fluid_*.vtk"),
        key=frame_index,
    )
    if not particle_files:
        raise SystemExit(f"no particle VTK files found in {vtk_dir}")

    surfaces = args.sequence_output / "surfaces"
    surfaces.mkdir(parents=True, exist_ok=True)

    records = []
    for blender_frame, source in enumerate(particle_files, start=1):
        source_index = frame_index(source)
        vtk = meshio.read(source)
        particles = np.asarray(vtk.points, dtype=np.float64)
        if len(particles) < 100:
            raise SystemExit(f"too few particles in {source}: {len(particles)}")

        threshold, mesh, diagnostics = reconstruct_one(particles)
        diag_text = ", ".join(
            f"t={t}:v={nv}:f={nt}" for t, nv, nt in diagnostics
        )
        print(
            f"SEQUENCE_RECON source={source.name} source_frame={source_index} "
            f"blender_frame={blender_frame} particles={len(particles)} {diag_text}"
        )
        if mesh is None or threshold is None:
            raise SystemExit(f"surface reconstruction empty for {source}: {diag_text}")

        out = surfaces / f"surface_{blender_frame:04d}.obj"
        mesh.write_to_file(str(out), file_format="obj")
        record = {
            "blender_frame": blender_frame,
            "source_frame": source_index,
            "source_vtk": source.name,
            "surface_obj": out.name,
            "particles": len(particles),
            "threshold": threshold,
            "vertices": len(mesh.vertices),
            "faces": len(mesh.triangles),
            "bytes": out.stat().st_size,
        }
        records.append(record)
        print(
            f"SEQUENCE_SURFACE frame={blender_frame} "
            f"vertices={record['vertices']} faces={record['faces']} bytes={record['bytes']}"
        )

    manifest = {
        "format": 1,
        "fps": 12,
        "particle_radius": PARTICLE_RADIUS,
        "smoothing_length": SMOOTHING_LENGTH,
        "cube_size": CUBE_SIZE,
        "frames": records,
    }
    manifest_path = args.sequence_output / "surface-sequence.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"SEQUENCE_MANIFEST={manifest_path}")
    print(f"SEQUENCE_FRAMES={len(records)}")


if __name__ == "__main__":
    main()
