# SPH dam-break + floating cube

Minimal GitHub Actions proof of concept for using SPlisHSPlasH outside Blender and reusing the result in Blender later.

## What it tests

1. Run SPlisHSPlasH headlessly on a GitHub-hosted Ubuntu runner.
2. Simulate a small dam-break inside a box.
3. Couple the SPH fluid to one lightweight dynamic cube.
4. Export fluid particles and rigid-body meshes as time-series VTK.
5. Reconstruct the final liquid surface with pySplashSurf.
6. Validate that the cube really moved by comparing its first/last exported mesh centroid.
7. Publish a small final OBJ + summary under `results/sph-dam-break-cube/`; keep the full VTK sequence as an Actions artifact.

The scene intentionally uses a coarse particle radius (0.05 m) and a one-second simulation so the first Actions test stays cheap.

## Outputs

- `vtk/ParticleData_Fluid_*.vtk` — fluid particle sequence including velocity/density.
- `vtk/rb_data_1_*.vtk` — dynamic cube mesh sequence.
- `rigid_bodies/` — SPlisHSPlasH rigid-body binary cache.
- `surface-final.obj` — final-frame surface reconstructed by pySplashSurf.
- `summary.json` — validation metrics.

The next useful step after this PoC is to convert the VTK/OBJ sequence to a Blender-friendly reusable animation cache (Alembic/USD or Blender sequence loader), rather than re-running the SPH solve.
