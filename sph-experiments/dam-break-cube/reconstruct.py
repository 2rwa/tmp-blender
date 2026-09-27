from __future__ import annotations

import argparse
from pathlib import Path

import meshio
import numpy as np
import pysplashsurf


PARTICLE_RADIUS = 0.05
SMOOTHING_LENGTH = 2.0 * PARTICLE_RADIUS
CUBE_SIZE = 0.5 * PARTICLE_RADIUS
THRESHOLDS = (0.6, 0.5, 0.4, 0.3, 0.2)


def estimate_spacing(points: np.ndarray, sample_size: int = 256) -> float:
    sample = points[: min(sample_size, len(points))]
    best = []
    for p in sample:
        d2 = np.sum((points - p) ** 2, axis=1)
        d2 = d2[d2 > 1.0e-16]
        if len(d2):
            best.append(float(np.sqrt(np.min(d2))))
    return float(np.median(best)) if best else float("nan")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    vtk_dir = args.output_dir / "vtk"
    particle_files = sorted(vtk_dir.glob("ParticleData_Fluid_*.vtk"))
    if not particle_files:
        raise SystemExit(f"no particle VTK files found in {vtk_dir}")

    source = particle_files[-1]
    input_mesh = meshio.read(source)
    particles = np.asarray(input_mesh.points, dtype=np.float64)
    if len(particles) < 100:
        raise SystemExit(f"too few fluid particles for reconstruction: {len(particles)}")

    print(f"RECONSTRUCT_SOURCE={source}")
    print(f"RECONSTRUCT_PARTICLES={len(particles)}")
    print(f"RECONSTRUCT_AABB_MIN={particles.min(axis=0).tolist()}")
    print(f"RECONSTRUCT_AABB_MAX={particles.max(axis=0).tolist()}")
    print(f"RECONSTRUCT_ESTIMATED_SPACING={estimate_spacing(particles):.9f}")
    print(f"RECONSTRUCT_POINT_DATA_KEYS={sorted(input_mesh.point_data.keys())}")
    for name, values in input_mesh.point_data.items():
        arr = np.asarray(values)
        if arr.size and np.issubdtype(arr.dtype, np.number):
            print(
                f"RECONSTRUCT_POINT_DATA_{name}="
                f"shape={arr.shape} min={float(np.min(arr)):.9g} "
                f"max={float(np.max(arr)):.9g}"
            )

    chosen = None
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
        raw = reconstruction.mesh
        nv = len(raw.vertices)
        nt = len(raw.triangles)
        densities = reconstruction.particle_densities
        if densities is not None and len(densities):
            dmin = float(np.min(densities))
            dmax = float(np.max(densities))
        else:
            dmin = float("nan")
            dmax = float("nan")
        diagnostics.append((threshold, nv, nt, dmin, dmax))
        print(
            f"RECONSTRUCT_TRIAL threshold={threshold:.3f} "
            f"vertices={nv} triangles={nt} "
            f"density_min={dmin:.9g} density_max={dmax:.9g}"
        )
        if nv > 0 and nt > 0:
            chosen = (threshold, raw)
            break

    if chosen is None:
        details = "; ".join(
            f"t={t}:v={nv}:f={nt}:rho={dmin:.6g}-{dmax:.6g}"
            for t, nv, nt, dmin, dmax in diagnostics
        )
        raise SystemExit(f"all SplashSurf reconstruction trials were empty: {details}")

    threshold, raw_mesh = chosen
    out = args.output_dir / "surface-final.obj"
    raw_mesh.write_to_file(str(out))
    print(f"RECONSTRUCT_THRESHOLD={threshold}")
    print(f"RECONSTRUCT_VERTICES={len(raw_mesh.vertices)}")
    print(f"RECONSTRUCT_TRIANGLES={len(raw_mesh.triangles)}")
    print(f"RECONSTRUCT_OUTPUT={out}")


if __name__ == "__main__":
    main()
