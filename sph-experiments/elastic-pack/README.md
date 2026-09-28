# Elastic SPH sample pack

Five lightweight visual probes using SPlisHSPlasH 2.18.1 elasticity solvers.

- `peer-soft-cube-drop`: Peer et al. 2018, soft cube drop
- `kugelstadt-stiff-cube-drop`: Kugelstadt et al. 2021, stiffer cube drop
- `cantilever-beam`: fixed-left beam under gravity
- `fixed-column-kick`: fixed-root vertical column with lateral initial velocity
- `elastic-block-collision`: two deformable blocks colliding head-on

These are intentionally qualitative first-pass tests, not controlled material validation. The first pass uses particle radius 0.04, 2 seconds, 12 FPS, and lightweight Geometry Nodes point rendering.
