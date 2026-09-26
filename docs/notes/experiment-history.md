# Experiment and Implementation History

Updated: 2026-09-26

This file is a dated engineering log rather than a stable specification.

## Bootstrap and shared pipeline

The repository began as a simple Blender rendering test and was reorganized into independent experiment folders with a shared Actions pipeline.

Early work established:

- portable Blender 4.0.2 instead of reinstalling Blender every run,
- shared Blender runtime cache,
- Xvfb for headless rendering,
- experiment discovery from changed folders,
- raw render checkpoints before validation,
- content-hash cache keys,
- persistent lightweight results,
- GitHub Pages gallery generation.

### Important failures that shaped the pipeline

**Portable Blender EGL failure**

Portable Blender initially aborted in Actions with `EGL_BAD_PARAMETER` / missing current GLX or EGL context. Running Blender through Xvfb with software GL fixed the headless runtime.

**Validator causing rerender**

The first fire animation rendered successfully but failed because the validator required an arbitrary 100 KiB minimum MP4 size. The actual file was roughly 96 KiB.

The pipeline was changed so raw render output is checkpointed immediately after Blender finishes and before validation. Validator-only changes therefore do not need to destroy expensive work.

**Cache key tied to run ID**

The first render checkpoint design used the workflow run ID, making it useless across later validator fixes. It was replaced by a content hash based on render inputs and Blender version.

**Python bytecode destabilizing cache keys**

`__pycache__` / `.pyc` files could alter the render-input hash. They are now explicitly excluded.

**Portable API differences**

Blender Python APIs are version-specific. Current experiments target Blender 4.0.2 and should be tested against that exact runtime before assuming newer/older API names work.

## Experiments

### orbital-sculpture

Baseline still-image smoke test.

Used for validating the shared Blender runtime and shared pipeline changes.

### water-dump

A lightweight water-like pour animation.

This experiment intentionally does not use full Mantaflow. It combines an Ocean surface, continuous stream, falling droplets, and splash elements to produce a cheap water-like animation.

It served as an early animation/MP4/validation test.

### fire-column

A lightweight stylized flame animation.

It uses emissive geometry, glow, lights, and sparks rather than a fluid volume simulation.

The initial successful render produced an MP4 below the validator's arbitrary 100 KiB threshold, motivating render checkpoints before validation.

### fluid-dam-break

First real Mantaflow liquid experiment.

Configuration:

- Blender 4.0.2
- liquid domain
- FLIP simulation
- resolution max 32
- 42 frames at 24 fps
- Modular cache
- explicit Data bake followed by Mesh bake
- center obstacle and low barrier

Successful Actions run: #15.

Observed outputs:

- MP4: 168,055 bytes
- Mantaflow cache: 6,947,010 bytes
- `fluid-sim.blend`: 924,008 bytes
- `fluid-result.blend`: 1,126,204 bytes

Both `.blend` files were small enough to commit directly to Git. The approximately 6.95 MiB fluid cache remained in Actions cache/artifact storage.

Two Blender files are deliberately produced:

- `fluid-sim.blend`: editable Mantaflow setup saved after baking
- `fluid-result.blend`: representative liquid mesh frozen into a self-contained scene for easier inspection without the external cache

### rigid-sphere-impact-1000

Current rigid-body stress/visual experiment.

Design:

- 1000 active cubes in a 10 x 10 x 10 stack
- one 18 kg active sphere dropped from above
- passive floor, left/right walls, and rear wall
- camera side intentionally open so debris can move toward the viewer
- 72 frames at 24 fps
- two `.blend` outputs plus MP4/poster

Actions run #16 failed immediately before expensive work because Blender 4.0.2 `RigidBodyWorld` does not expose `steps_per_second`.

The experiment was corrected to use:

```python
rigid_body_world.substeps_per_frame = 10
rigid_body_world.solver_iterations = 25
```

Actions run #17 was started with the corrected API. At the time this document was written, it had passed preflight/runtime verification and was still in the long `Build scene` stage. The workflow was intentionally left running without blocking the conversation.

## GitHub Pages

The Pages gallery was added after experiment output became easier to inspect through a public browser.

The gallery is generated from committed `results/` and provides preview images, playable short MP4s, validation summaries, source/result links, and links to committed Blender files.

A one-shot migration imported the existing Fire Column and Water Dump MP4 files from successful Actions artifacts so they could be played directly from Pages without rerendering.

## Storage policy history

The first `.blend` Git publication limit was 10 MiB. That was intentionally conservative.

The repository was later explicitly classified as a disposable public test repository, so the threshold was raised to 95 MiB per file. Storage growth is currently acceptable; useful content can be copied out and the repository can be cleaned or discarded later.

A separate local cleanup batch is planned rather than constraining experiments during this conversation.
