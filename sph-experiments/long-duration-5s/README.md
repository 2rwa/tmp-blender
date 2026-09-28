# SPH 5-second / long-duration scale test

This experiment keeps the proven 1800-particle dam-break scene and changes only the duration:

- previous baseline: about 1 second / 13 exported frames
- this test: 5 seconds / expected about 61 exported frames
- export FPS: 12

It also replaces the large intermediate OBJ sequence with compressed NPZ surfaces.

Pipeline:

```text
SPlisHSPlasH VTK
  -> pySplashSurf
  -> compressed surface_XXXX.npz
  -> direct OpenUSD authoring
     /FluidSurface
     /DynamicCube
  -> Blender Mesh Sequence Cache
  -> full-frame validation
  -> 5-second render
  -> Pages
```

The goal is to measure temporal scaling and observe the dynamic cube after it reaches the far tank wall, without mixing in a particle-count increase yet.
