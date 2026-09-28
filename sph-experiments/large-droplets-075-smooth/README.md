# SPH large droplets + Taubin smoothing

This is a pure mesh-postprocessing comparison built on the successful
`large-droplets-075` result.

No SPH simulation and no pySplashSurf reconstruction are rerun.

Input:

- particle radius used by source surface: 0.075
- smoothing length used by source surface: 0.15
- 61-frame compressed NPZ surface sequence

Postprocess:

- Taubin smoothing
- 5 iterations
- lambda = 0.45
- mu = -0.47
- topology preserved

Pipeline:

```text
large-droplets-075 NPZ
  -> Taubin smoothing
  -> smoothed NPZ
  -> direct USD
  -> Blender
  -> validation + render + Pages
```

The goal is to keep the newly visible larger droplets/water masses while
removing some of the small high-frequency surface roughness without the
shrinkage typical of simple Laplacian smoothing.
