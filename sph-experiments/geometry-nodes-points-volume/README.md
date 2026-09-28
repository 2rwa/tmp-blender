# SPH point cloud -> Blender Geometry Nodes

This experiment keeps the SPH particles as the primary representation instead
of baking every frame to a pySplashSurf surface mesh.

Pipeline:

```text
SPlisHSPlasH VTK particles
  -> compact NPZ point cache
  -> direct USD vertex-only animated mesh
  -> Blender Mesh Sequence Cache
  -> Geometry Nodes
       Mesh to Points
       Points to Volume
       Volume to Mesh
  -> material + render
```

Geometry Nodes exposes three modifier controls:

- Radius (default 0.10)
- Voxel Size (default 0.04)
- Threshold (default 0.10)

The saved Blend should therefore be useful as an interactive lab for changing
the surface interpretation without rebuilding SPH or pySplashSurf meshes.

The point cache also preserves velocity and density in NPZ for future
experiments, although v1 only feeds particle position into Geometry Nodes.
