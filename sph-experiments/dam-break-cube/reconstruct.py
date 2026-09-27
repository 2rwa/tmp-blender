from __future__ import annotations

import argparse
from pathlib import Path

import meshio
import numpy as np
import pysplashsurf


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    vtk_dir = args.output_dir / "vtk"
    particle_files = sorted(vtk_dir.glob("ParticleData_Fluid_*.vtk"))
    if not particle_files:
        raise SystemExit(f"no particle VTK files found in {vtk_dir}")

    source = particle_files[-1]
    mesh = meshio.read(source)
    particles = np.asarray(mesh.points, dtype=np.float64)
    if len(particles) < 100:
        raise SystemExit(f"too few fluid particles for reconstruction: {len(particles)}")

    mesh_with_data, _ = pysplashsurf.reconstruction_pipeline(
        particles,
        particle_radius=0.05,
        rest_density=1000.0,
        smoothing_length=2.0,
        cube_size=0.5,
        iso_surface_threshold=0.6,
        mesh_smoothing_weights=True,
        mesh_smoothing_weights_normalization=13.0,
        mesh_smoothing_iters=8,
        normals_smoothing_iters=5,
        mesh_cleanup=True,
        compute_normals=True,
        subdomain_grid=True,
        subdomain_num_cubes_per_dim=32,
        output_mesh_smoothing_weights=False,
    )

    out = args.output_dir / "surface-final.obj"
    mesh_with_data.write_to_file(str(out))
    print(f"RECONSTRUCT_SOURCE={source}")
    print(f"RECONSTRUCT_PARTICLES={len(particles)}")
    print(f"RECONSTRUCT_OUTPUT={out}")


if __name__ == "__main__":
    main()
