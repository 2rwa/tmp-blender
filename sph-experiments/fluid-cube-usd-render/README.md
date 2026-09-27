# SPH fluid + dynamic cube — combined USD render

This experiment packages the already-validated topology-changing fluid cache and the dynamic rigid-body cube into one USD file and renders them together in Blender.

Pipeline:

```text
fluid-direct-single.usdc
  + rigid_body_sequence.json
  -> /FluidSurface + /DynamicCube
  -> fluid-cube.usdc
  -> Blender 4.0.2
  -> 2 mesh objects, both cache-driven
  -> 13-frame validation
  -> preview + MP4 + portable Blend
```

The rigid-body sequence was extracted from the successful SPlisHSPlasH run #10 artifact before its expiration and is committed as JSON for reproducibility.
