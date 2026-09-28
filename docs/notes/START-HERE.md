# START HERE — tmp-blender handoff / 再開ガイド

Updated: 2026-09-28

This is the first file to read when resuming work on `2rwa/tmp-blender`.

`2rwa/tmp-blender` の作業を再開するときは、まずこのファイルを読んでください。

## Repository

- GitHub: https://github.com/2rwa/tmp-blender
- Pages gallery: https://2rwa.github.io/tmp-blender/
- Default branch: `main`
- Purpose: disposable public Blender experiment repository driven by GitHub Actions
- Current Blender runtime: Blender 4.0.2 on GitHub-hosted Linux runner via Xvfb/software GL

This repository is intentionally allowed to grow during experiments. Useful work can later be copied elsewhere, and repository cleanup can be handled separately.

このrepoは一時的な公開テスト用です。通常の実験では容量最適化を優先せず、必要な成果物の整理やrepo掃除は別作業として扱います。

## Current state

### Latest completed infrastructure / fluid PoC

A SPlisHSPlasH-based non-Blender fluid pipeline now runs successfully on GitHub Actions.

Successful baseline:

- workflow: `SPH fluid sample`
- Actions run: #10 / id `36328372215`
- 1800 SPH fluid particles
- 13 fluid VTK frames
- 13 dynamic rigid-body frames
- corrected dynamic cube frame 1 -> frame 13 displacement: about 2.007 m
- the old 1.366636 m figure was caused by lexicographic frame ordering and was frame 1 -> frame 9
- corrected regression run #13: cube frame 1 -> 13 displacement 2.007310 m
- corrected true-final pySplashSurf surface: 207,276 vertices / 407,352 faces
- corrected true-final OBJ: 20,799,581 bytes
- native SPlisHSPlasH 2.18.1 build is cached for later runs

Read first for this branch of work:

`docs/notes/sph-actions-poc-2026-09-28.md`

Critical points:

- use the native C++ `SPHSimulator`, not the PyPI `pysplishsplash` wheel on the current Actions runner,
- pass the scene path as an absolute path,
- explicitly request `file_format="obj"` from pySplashSurf,
- preserve run #10 as the regression baseline.

### Latest completed SPH -> Blender sequence replay

The external-fluid-to-Blender path is now proven end-to-end.

Successful workflow:

- `SPH Blender surface sequence`
- run #1 / id `36329404518`
- 13 surface frames reconstructed from SPH VTK
- 49,560 .. 59,258 vertices per frame
- 91,920 .. 111,316 faces per frame
- saved `surface-sequence.blend`: 59,273,460 bytes
- saved Blend reopened and validated in a fresh Blender process
- exactly one expected fluid mesh visible on every one of the 13 frames
- validation errors: 0

Persistent result:

`results/sph-dam-break-blender-sequence/`

Detailed history:

`docs/notes/sph-actions-poc-2026-09-28.md`

The next natural step is to compare the current 13-object baseline against Alembic/USD or another compact topology-changing animation cache.

### Preferred SPH -> Blender architecture

The compact cache path is now proven beyond the 13-object prototype.

Successful direct-USD results:

- one topology-changing `/FluidSurface` USD mesh -> Blender as one `MESH_SEQUENCE_CACHE` object
- synchronized `/FluidSurface` + `/DynamicCube` -> Blender as exactly two cache-driven mesh objects
- 13-frame fluid+cube replay validation errors: 0
- combined USD: about 15.30 MB
- portable Blend: about 5.61 MB
- dynamic cube frame 1 -> 13 displacement: about 2.007 m
- result published in `results/sph-fluid-cube-usd-render/` and on Pages

Preferred path:

```text
SPlisHSPlasH
  -> VTK
  -> pySplashSurf
  -> direct OpenUSD
  -> Blender Mesh Sequence Cache
```

For longer sequences, use compressed NPZ as the intermediate surface cache
rather than an OBJ-per-frame sequence.

### Current SPH scale test

Workflow: `SPH 5s scale test`

Current run to inspect first:

- run #3
- Actions id `36360959609`
- source commit `6402eff697c16215d068bd7c4ba5a3a278579ce4`

Goal:

- hold particle count near the 1800-particle baseline,
- extend simulation from ~1 second / 13 frames to 5 seconds / ~60 frames,
- measure surface-cache/USD/Blend growth and playback,
- observe the cube after reaching the far tank wall.

Run #1 and #2 showed that CLI `--stopAt 5.0` did not override the
scene's one-second stop for this setup. Run #3 generates a temporary scene
beside the original and directly sets `Configuration.stopAt = 5.0`.

Run #3 completed successfully:

- **61 frames** covering a 5.0-second simulated span
- 1800 particles
- SPH simulation: **12.53 s**
- surface reconstruction: **13.93 s**
- compressed NPZ surfaces: **51.41 MB**
- direct USD: **70.70 MB**
- portable Blend: **5.64 MB**
- all-frame scrub: **1.306 s**
- render: **415.09 s**
- validation errors: **0**
- Cube path length: **2.589 m**
- Cube X-direction reversals: **2**
- result published under `results/sph-long-duration-5s/`
- Pages gallery deployment succeeded

This proves the direct-USD architecture scales from 13 to 61 frames without
increasing Blender object count: one fluid cache object + one dynamic cube
cache object.

Read:

`docs/notes/sph-actions-poc-2026-09-28.md`

### Latest completed Blender visual experiment


The most recent completed experiment is:

`rigid-sphere-impact-1000-transparent-v2`

It is a higher-quality follow-up to `rigid-sphere-impact-1000`.

Configuration:

- 1000 active rigid-body cubes
- one 22 kg active impact sphere
- floor + three transparent physical containment walls
- front/camera side open
- 960 × 540
- 96 frames
- 24 fps
- `RigidBodyWorld.substeps_per_frame = 12`
- `RigidBodyWorld.solver_iterations = 30`

GitHub Actions run #18 completed successfully:

https://github.com/2rwa/tmp-blender/actions/runs/36219589354

Published result:

https://github.com/2rwa/tmp-blender/tree/main/results/rigid-sphere-impact-1000-transparent-v2

Observed validation:

- MP4: 459,528 bytes
- duration: 4.0 s
- preview: 960 × 540
- `rigid-sim.blend`: 9,613,412 bytes
- `rigid-result.blend`: 9,613,412 bytes
- both `.blend` files are committed to Git
- Pages deployment succeeded


## Previous experiments

### orbital-sculpture

Baseline still-image smoke test.

### water-dump

Cheap water-like animation using Ocean + procedural/animated geometry. Not a full Mantaflow simulation.

### fire-column

Cheap stylized flame animation using emissive geometry/glow/sparks. Not a full Mantaflow gas simulation.

### fluid-dam-break

Actual Mantaflow liquid simulation.

- FLIP liquid
- resolution max 32
- Data bake + Mesh bake
- run #15 succeeded
- two Blender files published to Git
- large simulation cache kept outside Git

### rigid-sphere-impact-1000

First 1000-body impact version.

- 1000 cubes
- one 18 kg sphere
- opaque side/rear walls
- 640 × 360
- 72 frames
- run #17 succeeded
- result and two `.blend` files published to Git

The opaque walls were visually distracting, which motivated transparent-wall v2.

## Critical operating rules

### Long-running tasks

For simulations/renders likely to take more than roughly 30 seconds:

1. commit/push experiment changes,
2. verify Actions discovery and cheap preflight,
3. check for immediate Blender/Python/API failures,
4. once real long-running simulation/render work has started, stop polling continuously,
5. inspect the run later rather than keeping an interactive session blocked.

Do not waste time repeatedly polling a long Actions job.

### Expensive work checkpointing

The workflow intentionally saves the raw render checkpoint before validation.

If rendering succeeds but validation fails:

- do not rerender automatically,
- fix `validate.py` where possible,
- validator/README/manifest files are excluded from the expensive render hash,
- reuse the saved render checkpoint.

### Blender API version

Target Blender 4.0.2 exactly. Do not assume API names from newer Blender releases.

Known examples:

- RigidBodyWorld: use `substeps_per_frame`, not `steps_per_second`
- prior experiments also encountered version-specific modifier/property differences

### Result publishing

Experiment manifest may contain:

```json
"repo_blends": [
  "example-sim.blend",
  "example-result.blend"
]
```

Current thresholds/policy:

- selected `.blend` files up to 95 MiB/file -> Git
- MP4 up to 5 MiB -> `results/<id>/media.mp4` for Pages
- large caches/intermediates -> Actions cache/artifact
- repository growth is acceptable for this temporary repo

## Pipeline overview

`.github/workflows/blender-experiment.yml`

Stages:

1. `discover`
2. `render`
3. `publish`
4. `pages` / `deploy_pages`

Important tooling:

- `tools/experiment.py`
  - experiment discovery
  - output checks
  - result publishing
  - selected `.blend` Git publication
- `tools/build_pages.py`
  - root/docs gallery generation

A change under one `experiments/<id>/` folder should normally run only that experiment.

Shared workflow/tool-only changes use `orbital-sculpture` as a smoke test.

## Licensing

Default:

- code/scripts/workflows/HTML: MIT-0
- generated Blender files/images/video/assets: CC0-1.0
- third-party data/assets/source material: original license/terms apply

See:

- `LICENSE`
- `LICENSES/`

Do not relicense third-party material that the repository authors do not control.

## Where to read next

- Architecture: `docs/notes/architecture.md`
- Experiment/history log: `docs/notes/experiment-history.md`
- Operational rules: `docs/notes/operations.md`
- SPH / Actions PoC: `docs/notes/sph-actions-poc-2026-09-28.md`

## Suggested next directions

There is no mandatory pending task. The current transparent-wall v2 is complete.

Natural next experiments include:

- actual Mantaflow smoke/fire (as opposed to the lightweight procedural fire-column)
- cloth over rigid bodies / wind interaction
- soft-body jelly collision
- Dynamic Paint ripples or wet trails
- particle/emitter stress tests
- Hair Curves / Geometry Nodes hair experiments
- larger rigid-body counts or alternative impact geometries

When starting a new experiment, create a new experiment ID rather than overwriting a successful prior experiment unless the user explicitly asks to revise it.

## Resume checklist

When resuming work:

1. read this file,
2. verify the current `main` branch,
3. check any relevant recent Actions run,
4. inspect the current result under `results/`,
5. continue from GitHub as the source of truth.

必要に応じて `architecture.md`、`experiment-history.md`、`operations.md` も参照してください。
