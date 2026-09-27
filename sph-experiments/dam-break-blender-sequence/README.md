# SPH surface sequence -> Blender replay

This experiment extends the successful `sph-dam-break-cube` Actions PoC.

Pipeline:

```text
SPlisHSPlasH VTK particle frames
  -> pySplashSurf surface OBJ for every frame
  -> Blender 4.0.2 imports all topology-changing meshes
  -> one mesh is visible per timeline frame
  -> saved .blend + preview + MP4
```

The Blender file intentionally stores each topology-changing surface as a separate mesh object and animates object scale with CONSTANT interpolation. This is a simple persistence-friendly proof that the cached external fluid simulation can be replayed in Blender without Mantaflow.

The next step after this succeeds is to evaluate a more compact cache/interchange format such as Alembic or USD.
