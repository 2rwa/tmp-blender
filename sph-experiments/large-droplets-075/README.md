# SPH large-droplet surface reconstruction — radius 0.075

Visual-only comparison against the successful 5-second baseline.

Physics is **not** rerun. The workflow downloads the already successful
`SPH 5s scale test #3` artifact and reuses its particle / rigid-body VTK
sequence.

Only the surface reconstruction changes:

```text
baseline:
  particle_radius = 0.05
  smoothing_length = 0.10
  cube_size = 0.05

large-droplet variant:
  particle_radius = 0.075
  smoothing_length = 0.15
  cube_size = 0.05
```

This isolates the visual effect of a 1.5x reconstruction radius from the SPH
physics itself.

The result is rebuilt as compressed NPZ -> direct USD -> Blender and rendered
with the same 61-frame / 5-second presentation path as the baseline.
