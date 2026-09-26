# Metaball Fountain 100 EEVEE

A first stress/visual test for Blender metaballs in the existing headless GitHub Actions movie pipeline.

## Experiment

- 100 metaball elements in one MetaBall datablock.
- Elements are emitted over frames 1–72.
- Deterministic ballistic motion, gravity, basin wall reflection, and damped floor bounces.
- Each element directly keyframes its metaball coordinate.
- Nearby elements fuse into one smooth implicit surface.
- Metallic cyan/mercury-like material.
- 480x360, 24 fps, 144 frames / 6 seconds.
- Existing prepared Blend -> parallel PNG chunks -> ffmpeg assembly pipeline.

The motion layer is intentionally simple and deterministic. This run is primarily testing metaball animation, fusion, rendering cost, and headless reliability rather than Blender's particle solver.

## Validation

The validator checks both media output and scene semantics:

- exactly 100 metaball elements;
- hundreds of animation F-curves and tens of thousands of keyframe points;
- a real fountain arc (max height);
- basin bounce activity;
- many active droplets by the preview frame;
- enough close pairs to make metaball fusion likely;
- complete 6-second MP4 output.

If this version is healthy, the next useful scaling step is 300 elements with the same scene and validation model.
