# SPH point-cloud rendering / Geometry Nodes notes — 2026-09-28

## Why this branch exists

The 5-second SPlisHSPlasH experiment originally treated a reconstructed
surface mesh as the main downstream representation.

That worked, but later experiments showed that keeping the **SPH particles as
the primary data** is a much better fit for exploratory visualization.

The same 1800-particle / 61-frame solve has now been tested through three
presentation paths:

1. pySplashSurf surface mesh,
2. pySplashSurf large-droplet surface + Taubin smoothing,
3. point-cloud USD + Blender Geometry Nodes surface generation.

The point-cloud path is currently the most attractive interactive/exploratory
representation.

## Source simulation

Shared source:

- SPlisHSPlasH native 2.18.1
- 1800 particles
- 61 exported frames
- 12 fps
- 5.0 seconds simulated span
- source long-run workflow: `SPH 5s scale test`
- successful run: #3 / Actions id `36360959609`

The source VTK sequence contains enough information to preserve:

- particle position,
- velocity,
- density,
- rigid-body geometry.

## Large-droplet surface experiment

Experiment:

`sph-experiments/large-droplets-075/`

Successful workflow:

- `SPH large droplets 075`
- run #1 / Actions id `36362387414`

This intentionally reused the successful 5-second SPH VTK sequence. It did
**not** rerun the fluid physics.

Surface reconstruction parameters:

```text
baseline:
  particle_radius = 0.05
  smoothing_length = 0.10
  cube_size = 0.05

large-droplet:
  particle_radius = 0.075
  smoothing_length = 0.15
  cube_size = 0.05
```

Measured result:

- surface vertices/frame: **114,766 .. 116,800**
- surface faces/frame: **222,384 .. 226,400**
- compressed surface NPZ total: **128,952,028 bytes**
- direct USD: **191,451,188 bytes**
- Blend: **11,414,476 bytes**
- render: **781.988 s**
- validation errors: **0**

Compared with the radius-0.05 5-second baseline:

- NPZ size: about **2.51x**
- USD size: about **2.71x**
- render time: about **1.88x**

Visual result: the water/droplets became easier to see, but the denser surface
mesh became expensive.

## Taubin smoothing experiment

Experiment:

`sph-experiments/large-droplets-075-smooth/`

Successful workflow:

- `SPH large droplets 075 smooth`
- run #2 / Actions id `36364391725`

Run #1 failed immediately because the normal Python environment did not have
NumPy installed. The workflow now installs NumPy explicitly before smoothing.

The successful run reused the already reconstructed radius-0.075 NPZ meshes;
it did not rerun SPH or pySplashSurf.

Parameters:

```text
method      = Taubin
iterations  = 5
lambda      = 0.45
mu          = -0.47
```

Measured smoothing behavior:

- smoothing time: **153.193 s**
- average mean vertex displacement: **0.0008797 m**
- global maximum vertex displacement: **0.002176 m**
- average bounding-box volume ratio: **0.99855**
- topology preserved exactly
- render: **776.658 s**
- direct USD remained **191,451,188 bytes**
- Blend remained **11,414,476 bytes**

Conclusion:

Taubin smoothing behaved correctly and avoided noticeable global shrinkage,
but it did not reduce topology or cache size and the rendered pipeline stayed
expensive. It is useful as a quality post-process, not as the primary
representation.

## Point-cloud + Geometry Nodes experiment

Experiment:

`sph-experiments/geometry-nodes-points-volume/`

Successful workflow:

- `SPH Geometry Nodes point volume`
- run #1 / Actions id `36367596940`
- source commit: `040d3d6f57267785db7461a2ea9513e9faf8bf35`
- Actions wall-clock: about **3 min 55 s**

Pipeline:

```text
SPlisHSPlasH VTK
  -> compact NPZ point cache
       position
       velocity
       density
  -> direct USD
       vertex-only animated mesh
  -> Blender Mesh Sequence Cache
  -> Geometry Nodes
       Mesh to Points
       Points to Volume
       Volume to Mesh
       Set Material
  -> render
```

Geometry Nodes exposes:

- `Radius = 0.10`
- `Voxel Size = 0.04`
- `Threshold = 0.10`

These remain editable in the saved Blend.

### Point-cloud storage

For all 61 frames:

- particle count: **1800**
- compact NPZ point cache: **2,790,514 bytes**
- animated point USD: **1,327,136 bytes**
- editable Blend: **978,058 bytes**
- preview: **287,025 bytes**
- MP4: **408,136 bytes**

The point USD is roughly **1/144 the size** of the 191 MB large-droplet
surface USD.

### Timing

- USD authoring: **0.165 s**
- Blender USD import: **0.0014 s**
- representative Geometry Nodes validation: **0.071 s**
- 61-frame video render: **190.052 s**
- workflow wall-clock: about **235 s**

The render is about:

- **2.18x faster** than the radius-0.05 pySplashSurf baseline
  (415.09 s -> 190.05 s),
- **4.1x faster** than the radius-0.075 large-droplet mesh
  (781.99 s -> 190.05 s).

### Evaluated Geometry Nodes surface sizes

Representative frames:

| frame | source particles | GN vertices | GN faces |
| ---: | ---: | ---: | ---: |
| 1 | 1800 | 6,848 | 6,846 |
| 7 | 1800 | 20,042 | 20,034 |
| 13 | 1800 | 31,930 | 31,866 |
| 31 | 1800 | 19,324 | 19,328 |
| 46 | 1800 | 17,162 | 17,162 |
| 61 | 1800 | 15,428 | 15,424 |

Validation errors: **0**.

## Current architectural conclusion

For exploratory work, prefer:

```text
SPH particles as source of truth
  -> compact point cache
  -> presentation-specific interpretation
```

Then choose the presentation layer according to purpose:

### Blender / interactive authoring

```text
points
  -> Mesh to Points
  -> Points to Volume
  -> Volume to Mesh
```

Advantages:

- very small cache,
- much smaller Blend,
- Radius / Voxel Size / Threshold remain interactive,
- surface mesh is generated only when needed,
- easy to layer diagnostics on the same particles.

### pySplashSurf / offline surface

Keep pySplashSurf when a fixed higher-detail surface mesh is actually needed.

Advantages:

- explicit exportable topology,
- deterministic downstream mesh pipeline,
- useful for offline/high-detail presentation.

Tradeoff:

- surface topology can become very large,
- cache and render costs grow quickly with larger reconstruction radius.

### WebGPU / real-time visualization

The same particle representation is a strong candidate for WebGPU:

```text
particle buffer
  position
  velocity
  density
  acceleration (derived)
    -> compute density field / spatial grid
    -> raymarch or point/instance rendering
```

Avoid evaluating all particles at every ray step. A 3D density grid or spatial
hash should be the likely scalable path.

## Next diagnostic ideas

The current NPZ point cache already preserves velocity and density. Blender v1
only sends particle position into the animated USD.

Natural next experiments:

### Velocity arrows

For each particle:

- arrow origin = particle position,
- arrow direction = velocity direction,
- arrow length = speed,
- optionally decimate particles or show only fast particles.

Likely Geometry Nodes building blocks:

- Instance on Points,
- Align Euler to Vector,
- Scale Instances.

### Acceleration heat map

Derive:

```text
a[t] ~= (v[t] - v[t-1]) / dt
```

Then color points/arrows by acceleration magnitude.

Acceleration should probably be:

- clamped,
- optionally temporally smoothed,
- possibly displayed on a log or percentile scale,

because frame-to-frame particle acceleration may be visually noisy.

### Density / spray separation

Use density and/or speed to classify:

- dense continuous water,
- low-density spray,
- fast ejecta.

This can drive different point radius, material, arrows, or separate
rendering branches.

## Reuse rule

Do not rebuild the expensive surface mesh merely to inspect particle
behavior.

Prefer keeping:

```text
position + velocity + density (+ derived acceleration)
```

as the reusable core dataset, then generate meshes, volumes, arrows, trails,
or raymarched density fields downstream.
