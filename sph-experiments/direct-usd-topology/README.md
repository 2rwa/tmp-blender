# Direct topology-varying USD test

This test bypasses Blender's USD exporter and authors the USD mesh schema directly.

The file contains one `UsdGeom.Mesh` prim at `/FluidSurface`.

For frames 1..13 it authors time samples for:

- `points`
- `faceVertexCounts`
- `faceVertexIndices`

OpenUSD defines a mesh as topologically varying when the face-count/index topology attributes have multiple time samples. Blender's USD importer is then expected to attach a Mesh Sequence Cache modifier for animated geometry.

The source geometry remains the already-validated 13-frame SPH Blender replay result.
