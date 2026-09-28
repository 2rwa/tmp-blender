# Elastic burst-like SPH pack

Five high-energy probes on the already proven SPlisHSPlasH 2.18.1 elasticity pipeline:

- `burst-soft-floor-splat`
- `burst-stiff-floor-shock`
- `burst-head-on-smash`
- `burst-cantilever-whip`
- `burst-pseudo-cluster`

The pseudo cluster is **not fracture**: eight blocks are separate from the initial state and only arranged to look like one body.

This first pass uses particle radius 0.04, 0.0005 s timestep, 2 s duration, 12 FPS export, and the existing lightweight Blender Geometry Nodes point renderer.
