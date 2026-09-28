# Experiment and Implementation History

Updated: 2026-09-28

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

Actions run #17 completed successfully. The result was published to Git and Pages, including two approximately 8.84 MiB Blender files.

### rigid-sphere-impact-1000-transparent-v2

Follow-up created because the opaque containment walls in the first rigid-body version were visually distracting.

Instead of removing containment entirely, v2 keeps three physical walls but renders them as transparent/glass-like surfaces. This preserves the collision behavior while making the scene feel open.

Configuration:

- 1000 active cubes
- one 22 kg impact sphere
- transparent left/right/rear passive walls
- front/camera side open
- 960 x 540
- 96 frames at 24 fps
- rigid-body substeps: 12
- solver iterations: 30

Actions run #18 completed successfully.

Published outputs:

- MP4: 459,528 bytes
- duration: 4.0 seconds
- `rigid-sim.blend`: 9,613,412 bytes
- `rigid-result.blend`: 9,613,412 bytes


## GitHub Pages

The Pages gallery was added after experiment output became easier to inspect through a public browser.

The gallery is generated from committed `results/` and provides preview images, playable short MP4s, validation summaries, source/result links, and links to committed Blender files.

A one-shot migration imported the existing Fire Column and Water Dump MP4 files from successful Actions artifacts so they could be played directly from Pages without rerendering.

## Storage policy history

The first `.blend` Git publication limit was 10 MiB. That was intentionally conservative.

The repository was later explicitly classified as a disposable public test repository, so the threshold was raised to 95 MiB per file. Storage growth is currently acceptable; useful content can be copied out and the repository can be cleaned or discarded later.

Repository cleanup is intentionally treated as a separate maintenance task rather than constraining experiments.


## 2026-09-28 — SPlisHSPlasH GitHub Actions PoC

A non-Blender SPH fluid pipeline was added under `sph-experiments/dam-break-cube/`.

After several deliberate failures, Actions run #10 completed the full path:

`SPlisHSPlasH C++ SPHSimulator -> fluid + dynamic cube -> VTK time series -> pySplashSurf -> OBJ -> validation`.

Verified result:

- 13 fluid frames
- 13 dynamic rigid-body frames
- 1800 fluid particles
- corrected dynamic cube frame 1 -> frame 13 displacement: about 2.007 m
- original 1.366636 m report was frame 1 -> frame 9 due lexicographic VTK filename sorting
- final surface: 207,174 vertices / 407,148 faces
- final OBJ: 20,688,757 bytes

Key engineering findings:

- the PyPI `pysplishsplash` wheel segfaulted on GitHub-hosted Ubuntu 24.04 across multiple Python/NumPy/Xvfb combinations,
- the native C++ simulator builds successfully and is now cached,
- CLI relative scene paths are resolved from the executable directory, so the workflow passes absolute scene/output paths,
- pySplashSurf `write_to_file()` defaults to VTK42 even if the filename ends in `.obj`; `file_format="obj"` must be explicit.

Full notes:

`docs/notes/sph-actions-poc-2026-09-28.md`


## 2026-09-28 — direct USD topology cache

The 13 independent Blender mesh-object prototype was reduced to one
topology-varying USD mesh.

Successful workflow:

- `SPH direct USD topology cache`
- run #2 / id `36358344451`

Result:

- one USD prim: `/FluidSurface`
- 13 time samples for `points`, `faceVertexCounts`, and
  `faceVertexIndices`
- Blender imports one mesh object
- Blender attaches `MESH_SEQUENCE_CACHE`
- all 13 source topologies reproduced exactly
- replay errors: 0
- USD: 15,296,671 bytes
- imported Blend: 5,523,896 bytes

This became the preferred surface-cache representation.

## 2026-09-28 — synchronized SPH fluid + rigid cube

Successful workflow:

- `SPH fluid cube USD render`
- run #2 / id `36359942969`

The direct USD cache was extended to contain:

- `/FluidSurface`
- `/DynamicCube`

Blender imported exactly two cache-driven mesh objects.

Verified:

- 13 synchronized frames
- fluid topology correct on every frame
- cube topology: 8 vertices / 12 faces
- both objects use `MESH_SEQUENCE_CACHE`
- replay errors: 0
- cube frame 1 -> frame 13 displacement: 2.007184 m
- combined USD: 15,298,504 bytes
- portable Blend: 5,610,696 bytes
- preview + MP4 published to Pages

This also exposed a filename-ordering error in older validation code. VTK
sequence files must be sorted by parsed numeric frame suffix, never plain
lexicographic filename order.

## 2026-09-28 — 5-second temporal scale test

A new experiment keeps the ~1800-particle baseline but extends the simulation
to 5 seconds at 12 exported frames per second.

The intermediate surface representation was changed from OBJ-per-frame to
compressed NPZ before direct USD authoring.

Failure history:

- run #1 / `36360733632`: only 13 frames; CLI stop override did not extend the scene.
- run #2 / `36360827839`: options moved before the scene path, but still only 13 frames.
- run #3 / `36360959609`: generates a temporary scene beside the original and directly sets `Configuration.stopAt = 5.0`.

Run #3 has successfully completed the 5-second SPH solve, long-sequence
surface reconstruction, and compressed NPZ stage. At the time of this log
update, direct USD validation/render is still running.
