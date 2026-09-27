# SPH Blender cache format comparison

This experiment compares the successful 13-object Blender replay baseline against two interchange/cache containers:

- Alembic (`.abc`)
- USD Crate (`.usdc`)

Input:

`results/sph-dam-break-blender-sequence/surface-sequence.blend`

The SPH simulation is **not** rerun. The experiment only measures the presentation/cache layer.

## What is measured

- cache file size,
- export time,
- import time,
- time to scrub all 13 frames in headless Blender,
- imported Blender file size,
- number of imported mesh objects,
- timeline replay correctness.

The current baseline stores 13 independent topology-varying fluid meshes and switches them with constant transform animation. This comparison packages that already-proven representation into Alembic/USD. It does not yet collapse the sequence to a single topology-changing mesh primitive.

A later experiment can test a true single-mesh topology-changing cache after these container baselines are known.
