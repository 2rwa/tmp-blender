# Geometry Nodes Volume Flame v2 Cycles

Diagnostic comparison experiment for the v2 procedural flame using **Cycles CPU** instead of EEVEE.

The purpose is to isolate whether the washed-out / cloud-like appearance mainly comes from the renderer or from the Geometry Nodes / volume material setup.

## Profile

- 480 x 360
- 24 fps
- 48 frames / 2 seconds
- Cycles CPU
- 12 samples
- adaptive sampling enabled
- 12 frames per chunk
- denoising disabled for a more direct renderer comparison

The Geometry Nodes structure and material values stay close to the EEVEE v2 experiment. The shorter movie keeps GitHub Actions cost bounded while still showing temporal behavior.

## Interpretation

- If Cycles looks materially better with the same node/material setup, the renderer is a major contributor.
- If Cycles has the same washed-out / cloud-like look, the node density, emission, blackbody, point distribution, or motion design is the stronger cause.
