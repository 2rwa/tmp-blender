# SPH point diagnostics — Geometry Nodes

This experiment continues the point-cloud-first SPH branch.

It reuses the proven 5-second / 61-frame / 1800-particle SPlisHSPlasH output and
keeps the particle cache as the source of truth.

The experiment runs three Blender 4.0.2 variants in parallel:

- `velocity`: every 8th particle gets a Geometry Nodes velocity arrow; all
  particles remain visible as small blue points.
- `acceleration`: all particles are colored into five acceleration bands.
- `combined`: acceleration-colored particles plus sparse velocity arrows.

Acceleration is derived from cached velocity:

```text
a[t] = (v[t] - v[t-1]) / dt
```

The display normalization uses the global 97th percentile so a few spikes do
not dominate the whole color range.

## Attribute transport strategy

The previous point-volume proof only transported position through USD.

For this diagnostic experiment, do not depend on arbitrary USD primvars.
Instead the animated USD contains synchronized vertex-only carrier meshes:

```text
/SPHPoints
/ArrowPoints
/VelocityValues
/AccelerationValues
/DynamicCube
```

`VelocityValues` stores velocity vectors as carrier point coordinates.
`AccelerationValues` stores normalized acceleration magnitude in carrier X.

Geometry Nodes reads the corresponding carrier element with `Sample Index`,
using stable particle ordering.

This deliberately tests the visualization first while avoiding uncertainty
around Blender 4.0.2 custom USD primvar import behavior.

## Geometry Nodes path

Velocity:

```text
ArrowPoints
  -> Mesh to Points
  -> Index
  -> Sample Index(VelocityValues.Position)
  -> Align Euler to Vector
  -> Instance on Points
  -> Scale Instances by normalized speed
```

Acceleration:

```text
SPHPoints
  -> Mesh to Points
  -> Index
  -> Sample Index(AccelerationValues.Position.x)
  -> five threshold selections
  -> five fixed-color point instances
  -> Join Geometry
```

The workflow performs cheap Python syntax checks before the Blender jobs,
runs the three render variants concurrently, uploads each result as an
artifact, then uses one publish job to write persistent results back to GitHub.
