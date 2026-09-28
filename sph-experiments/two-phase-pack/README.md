# SPH two-phase sample pack

Five lightweight two-phase SPlisHSPlasH experiments.

Each phase is a real separate SPlisHSPlasH fluid model selected through `FluidBlock.id` and `Materials.id`. The two VTK streams are preserved separately (`ParticleData_PhaseA_*` and `ParticleData_PhaseB_*`), compacted to NPZ, authored as two animated vertex-only USD meshes, and rendered in Blender Geometry Nodes with distinct colors.

Cases:

- `stratified-oil-water` — heavy lower layer + lighter, more viscous upper layer
- `dual-dam-break` — two phases collapse from opposite sides and meet
- `heavy-drop-into-light-pool` — denser drop enters lighter pool
- `light-drop-into-heavy-pool` — lighter drop enters denser pool
- `opposed-two-phase-jets` — finite slugs with opposing initial velocities

First pass is intentionally cheap: 2 seconds, 12 exported FPS, particle radius 0.07 m, 640x360 render.
