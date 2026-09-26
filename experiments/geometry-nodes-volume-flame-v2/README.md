# Geometry Nodes Volume Flame v2

A fully new second-pass flame experiment for the tmp-blender GitHub Actions -> Colab workflow.

This version is intentionally not a small tweak of the first flame attempt. It rebuilds the effect as two separate Geometry Nodes volume layers:

- Outer flame: broader orange volume with stronger lateral sway.
- Core flame: narrower bright inner volume with lower sway and higher rise speed.

The goal is to keep the pre-render inexpensive while producing a flame silhouette that reads more clearly and avoids the washed-out, over-bright look of the previous attempt.

## Pre-render profile

- 480 x 360
- 24 fps
- 96 frames / 4 seconds
- requested EEVEE render samples: 16
- 24 frames per chunk
- PNG frame sequence with cache reuse
- .blend saved and committed before chunk rendering

## Validation goals

Compared to v1, validation checks luminance range, mean brightness, warm flame colors, and white-hot blowout ratio.

## License / ライセンス

Code in this experiment is MIT-0. Generated Blender files, renders, videos, and other generated assets are CC0-1.0 unless otherwise noted.
