# SPlisHSPlasH on GitHub Actions PoC — 2026-09-28

## Status

Completed successfully.

The proof of concept demonstrates a non-Blender fluid simulation pipeline running entirely on GitHub Actions:

```text
GitHub Actions
  -> SPlisHSPlasH 2.18.1 C++ SPHSimulator
  -> SPH fluid + dynamic rigid body
  -> VTK particle / rigid-body time series
  -> pySplashSurf 0.14.1.0
  -> final OBJ surface mesh
  -> validation + Actions artifact + lightweight Git result
```

Successful workflow run:

- workflow: `SPH fluid sample`
- run: **#10**
- Actions run id: **36328372215**
- source commit: `4872ecf07029668f13db448ad97b58a7b7b18c69`
- final README fix: `7e11c65073af723975edf677e0faaba0893737bf`

Primary files:

- `.github/workflows/sph-fluid-sample.yml`
- `sph-experiments/dam-break-cube/scene.json`
- `sph-experiments/dam-break-cube/models/UnitBox.obj`
- `sph-experiments/dam-break-cube/reconstruct.py`
- `sph-experiments/dam-break-cube/validate.py`
- `results/sph-dam-break-cube/`

## Verified result

Run #10 validated:

- fluid particle frames: **13**
- dynamic rigid-body frames: **13**
- fluid particles per checked frame: **1800**
- dynamic cube initial centroid: `[-0.1, 0.519852, 0.0]`
- dynamic cube final centroid from the numerically sorted run #10 artifact: `[1.873282, 0.153315, -0.024456]`
- corrected dynamic cube frame 1 -> frame 13 displacement: **2.007184 m**
- note: the original **1.366636 m** figure was frame 1 -> frame 9 because filenames had been sorted lexicographically
- final liquid surface vertices: **207,174**
- final liquid surface faces: **407,148**
- final OBJ size: **20,688,757 bytes**

This confirms that the dynamic cube actually moved substantially during the SPH simulation rather than merely being present in the scene.

The full particle and rigid-body time-series output is uploaded as the Actions artifact:

`sph-dam-break-cube`

The lightweight persistent result is stored under:

`results/sph-dam-break-cube/`

## Working build/runtime configuration

Do not use the PyPI `pysplishsplash` wheel for this Actions workflow.

The stable path found in this experiment is to build the native C++ simulator:

```text
SPlisHSPlasH: 2.18.1
runner: ubuntu-24.04 / x86_64
CMAKE_BUILD_TYPE=Release
USE_PYTHON_BINDINGS=OFF
USE_AVX=OFF
CI_BUILD=ON
target=SPHSimulator
```

Required Ubuntu packages used by the upstream Linux build path:

```text
xorg-dev
freeglut3-dev
```

The compiled tree is cached at:

`.cache/splishsplash-2.18.1`

After the first successful build, later runs restore this cache and skip the expensive C++ build.

## Critical gotchas

### 1. PyPI pysplishsplash wheel segfaulted on GitHub-hosted Ubuntu

Observed failures included:

- Python 3.12 + current NumPy
- Python 3.12 + NumPy 1.26.4
- Python 3.12 under Xvfb
- Python 3.10 + NumPy 1.26.4

In each case, importing or starting `pysplishsplash` segfaulted with exit code 139.

The upstream wheel CI builds manylinux wheels, but this experiment did not find a reliable runtime path on the GitHub-hosted Ubuntu 24.04 runner.

Decision for this repo:

**Use the native C++ `SPHSimulator`; do not spend more time on the wheel unless wheel compatibility itself becomes the research target.**

### 2. Relative scene paths are resolved against the executable directory

This failed:

```bash
.cache/splishsplash-2.18.1/bin/SPHSimulator \
  sph-experiments/dam-break-cube/scene.json
```

SPlisHSPlasH attempted to open:

```text
.cache/splishsplash-2.18.1/bin/sph-experiments/dam-break-cube/scene.json
```

and then failed.

Use absolute paths:

```bash
scene_file="$(realpath sph-experiments/dam-break-cube/scene.json)"
output_dir="$(realpath output/sph-dam-break-cube)"

.cache/splishsplash-2.18.1/bin/SPHSimulator \
  "$scene_file" \
  --no-gui \
  --no-cache \
  --no-initial-pause \
  --stopAt 1.0 \
  --output-dir "$output_dir"
```

Relative model paths inside the scene, such as `models/UnitBox.obj`, are resolved relative to the scene and can remain relative.

### 3. pySplashSurf write_to_file defaults to VTK42

This call is misleading:

```python
raw_mesh.write_to_file("surface-final.obj")
```

The filename says OBJ, but pySplashSurf's default `file_format` is `vtk42`.

The validator therefore saw an `.obj` file containing VTK data and counted zero OBJ vertices/faces.

Always specify the format:

```python
raw_mesh.write_to_file("surface-final.obj", file_format="obj")
```

### 4. Validate the real output, not just exit status

The experiment initially reached "surface reconstruction step exited successfully" while the validator still failed.

The final validation checks:

- multiple fluid VTK frames exist,
- multiple dynamic rigid-body frames exist,
- particle counts are nontrivial,
- the dynamic cube centroid changes,
- the final OBJ contains a large nonzero number of vertices/faces.

This caught the VTK-disguised-as-OBJ problem.

## Failure history

### Run #1

Failed in `actions/setup-python`.

Cause:

`cache: pip` was enabled without a supported dependency manifest such as `requirements.txt` or `pyproject.toml`.

Fix:

Remove the setup-python pip cache setting.

### Run #2

The wheel installed, but `splash --version` segfaulted.

This showed that installation success was not enough.

### Run #3

Switched from the CLI wrapper to the official Python API with `useGui=False`.

`import pysplishsplash` itself still segfaulted.

### Run #4

Pinned NumPy to 1.26.4.

Still segfaulted.

### Run #5

Ran under Xvfb/software GL.

Still segfaulted.

### Run #6

Dropped to Python 3.10.

Still segfaulted.

Decision: abandon the wheel path.

### Run #7

Built native C++ `SPHSimulator` successfully.

The executable was produced and cached, but the scene load failed because a relative scene path was resolved against the executable directory.

Important result:

**GitHub Actions can build SPlisHSPlasH 2.18.1 successfully.**

### Run #8

Absolute scene/output paths fixed the load problem.

SPH simulation succeeded and pySplashSurf ran, but validation reported zero OBJ vertices/faces.

This was initially investigated as a reconstruction-parameter problem.

### Run #9

Added detailed surface diagnostics.

Observed:

- 1800 particles
- final particle AABB approximately
  - min `[-1.9152, 0.0856, -0.9148]`
  - max `[1.4422, 1.8701, 0.9152]`
- estimated nearest-neighbor spacing: about `0.07235`
- VTK attributes: `density`, `id`, `velocity`
- exported density range: about `254.65 .. 1026.03`
- SplashSurf raw result at threshold 0.6:
  - **206,924 vertices**
  - **406,648 triangles**

This proved that the surface reconstruction itself was not empty.

Root cause was then found: pySplashSurf had written VTK42 data to a filename ending in `.obj`.

### Run #10

Explicit `file_format="obj"` fixed the final issue.

All workflow steps passed.

The persistent result was committed to Git.

## Current architecture

```text
source scene
  |
  v
SPHSimulator (cached native C++ build)
  |
  +--> vtk/ParticleData_Fluid_*.vtk
  |      position + velocity + density + id
  |
  +--> rigid-body VTK/BIN sequence
  |
  v
pySplashSurf
  |
  v
surface-final.obj
  |
  +--> validate.py
  |
  +--> Actions artifact: full cache
  |
  +--> Git: summary + final OBJ
```

This cleanly separates:

1. expensive physics,
2. particle/rigid-body cache,
3. surface reconstruction,
4. later Blender rendering.

Blender is not required for the SPH solve.

## Natural next experiment

The next useful test is:

**Reconstruct every fluid VTK frame into a surface mesh sequence and replay it in Blender without running a fluid solver in Blender.**

Suggested progression:

```text
v1: all 13 fluid frames -> OBJ sequence
v2: Blender loads/replays OBJ sequence
v3: convert/cache as Alembic or another animation cache
v4: preserve or import rigid-body transform/mesh sequence
v5: render water + carried object in Blender
```

Do not overwrite the successful one-frame PoC. Keep run #10 as the baseline regression case.

## Resume prompt

A new conversation should be able to resume with:

> Read `2rwa/tmp-blender/docs/notes/sph-actions-poc-2026-09-28.md` and continue from the latest SPH -> direct USD -> Blender work. Preserve the successful 13-frame direct-USD fluid+cube result as the regression baseline, and check the latest `SPH 5s scale test` run before continuing.


## 2026-09-28 follow-up — full surface sequence replay in Blender

The next-stage experiment also completed successfully.

Workflow:

- `SPH Blender surface sequence`
- run: **#1**
- Actions run id: **36329404518**
- source commit: `de73c54a996384de23cddebff903c95929649be7`
- persistent result commit: `52f4f6cb0338fd1a1914ceb56b6ea5bef36cf472`

Pipeline:

```text
SPlisHSPlasH
  -> 13 fluid VTK particle frames
  -> pySplashSurf reconstructs every frame
  -> 13 topology-changing OBJ surfaces
  -> Blender 4.0.2 imports all 13 meshes
  -> CONSTANT timeline switching, one fluid mesh visible per frame
  -> saved surface-sequence.blend
  -> reopen the saved Blend in a fresh Blender process
  -> validate all 13 timeline frames
  -> preview + MP4 + artifact + Git result
```

Verified sequence result:

- surface frames: **13**
- source frames: **1..13**
- vertices per frame: **49,560 .. 59,258**
- faces per frame: **91,920 .. 111,316**
- total OBJ sequence size: **62,451,074 bytes**
- saved Blender file: **59,273,460 bytes**
- preview PNG: **246,083 bytes**
- MP4: **31,499 bytes**

The saved Blend was reopened in a new Blender invocation and validated frame-by-frame.

Validation result:

- fluid objects in the Blend: **13**
- expected visible fluid objects per frame: **1**
- observed visible fluid objects per frame: **1**
- frame replay errors: **0**

This is important because it proves the Blender file itself contains a reusable topology-changing animation representation. The replay does not depend on the original SPH solver or on the OBJ files after the Blend has been saved.

### Blender representation used for the PoC

Each reconstructed surface is imported as an ordinary mesh object:

```text
FluidFrame_0001
FluidFrame_0002
...
FluidFrame_0013
```

Each object receives CONSTANT keyframes so that exactly one object has unit scale on its corresponding timeline frame while the others have zero scale.

This is intentionally simple rather than storage-efficient. It was chosen to prove persistence and replay before introducing a more compact cache format.

### Current proven separation

```text
physics stage:
  SPlisHSPlasH

surface stage:
  pySplashSurf

presentation stage:
  Blender
    - material
    - camera
    - lighting
    - rendering
```

Blender no longer needs to run Mantaflow or any fluid solver for this animation.

### Next natural step

The next useful experiment is no longer "can Blender replay the sequence?" — that is proven.

The next comparison should be:

```text
current baseline:
  13 independent Blender mesh objects
  59.3 MB Blend

vs.

candidate cache:
  Alembic and/or USD
```

Measure:

- cache size,
- Blender load time,
- timeline scrub behavior,
- render behavior,
- topology-changing mesh support,
- whether velocity attributes survive,
- whether rigid-body animation can be packaged beside the fluid,
- portability outside Blender.

Keep the current `surface-sequence.blend` result as the regression/reference case.


## 2026-09-28 follow-up — Alembic vs USD cache container comparison

Workflow:

- `SPH Blender cache format compare`
- run: **#1**
- Actions run id: **36330257527**
- source commit: `db3eeaba800e559a6115a6069b1ff286accd5aeb`

Input baseline:

- `surface-sequence.blend`
- size: **59,273,460 bytes**
- 13 independent fluid mesh objects
- 661,252 total stored vertices
- 1,228,920 total stored faces

### Alembic

- cache: **27,612,083 bytes**
- size vs source Blend: **46.6%**
- export: **0.0235 s**
- import: **0.1360 s**
- headless scrub through 13 frames: **0.0165 s**
- imported Blend: **62,930,336 bytes**
- imported mesh objects: **13**
- replay errors: **0**

### USD Crate

- cache: **16,529,185 bytes**
- size vs source Blend: **27.9%**
- export: **0.1062 s**
- import: **0.1957 s**
- headless scrub through 13 frames: **0.00155 s**
- imported Blend: **59,243,576 bytes**
- imported mesh objects: **13**
- replay errors: **0**

Both formats preserved all per-frame vertex/face counts exactly.

Observed conclusion for this specific 13-object representation:

- USD Crate is substantially smaller than Alembic.
- Alembic exported and imported somewhat faster in this tiny test.
- USD's measured headless 13-frame scrub loop was much faster, though this is a short synthetic benchmark and should not be over-generalized.
- Importing either cache back into Blender produced 13 mesh objects with cache-driven transform behavior; neither test collapsed the representation to one topology-changing mesh.

This comparison is therefore a **container baseline**, not yet the final topology-changing cache architecture.

Persistent result:

`results/sph-cache-format-compare/`

Next experiment:

Create a single Blender mesh object whose evaluated mesh topology changes per frame, export that animation to Alembic and USD, then verify after re-import that:

- exactly one mesh object exists,
- vertex/face counts match the 13 source frames,
- frame scrubbing works,
- cache size/load behavior can be compared with the 13-object baseline.


## 2026-09-28 direct USD topology test — important intermediate result

The first direct-authoring run exposed a tooling bug in the test harness but also proved the core architecture.

Actions run:

- workflow: `SPH direct USD topology cache`
- run #1: `36358215899`

The direct USD file was successfully written before the metrics script hit an OpenUSD Python API compatibility error.

Blender then re-imported that file successfully and observed:

- imported mesh objects: **1**
- modifier: **MESH_SEQUENCE_CACHE**
- replay validation errors: **0**
- all 13 frames reproduced the exact source vertex/face counts

This proves that a single USD Mesh prim with time-sampled `points`,
`faceVertexCounts`, and `faceVertexIndices` is a working compact
representation for the topology-changing SPH surface in Blender 4.0.2.

The run failed later only because OpenUSD 23.05 exposes
`UsdAttribute.GetTimeSamples()` as a zero-argument function returning the
sample list, while the first script used an output-list argument form.

Additional CI lesson:

Blender may exit with code 0 after a Python traceback unless
`--python-exit-code 1` is supplied. Future Blender-based validation commands
for this path use that option in addition to shell `pipefail`.


## 2026-09-28 direct topology-varying USD — success

Workflow:

- `SPH direct USD topology cache`
- run: **#2**
- Actions run id: **36358344451**
- source commit: `ec9ca0d634c7ef48e1d298489a969696db95a293`

This run completed successfully and establishes a compact single-object topology-changing cache for the SPH surface.

### Direct USD structure

The cache contains one USD mesh prim:

`/FluidSurface`

with 13 time samples each for:

- `points`
- `faceVertexCounts`
- `faceVertexIndices`

Time samples are exactly frames 1 through 13.

### Blender re-import validation

Blender 4.0.2 imported the cache as:

- mesh objects: **1**
- modifier: **MESH_SEQUENCE_CACHE**
- replay errors: **0**

All 13 frames reproduced the exact original topology counts.

Examples:

- frame 1: 54,000 vertices / 100,800 faces
- frame 2: 59,258 vertices / 111,316 faces
- frame 13: 49,708 vertices / 92,220 faces

### Size / timing

Direct single-mesh USD:

- cache size: **15,296,671 bytes**
- direct authoring time: **3.658 s**
- Blender import time: **0.0498 s**
- 13-frame headless scrub: **0.1966 s**
- imported Blend size: **5,523,896 bytes**

13-object USD baseline:

- cache size: **16,529,185 bytes**
- imported Blend size: **59,243,576 bytes**

Direct single-mesh USD is about **92.5%** of the 13-object USD cache size, but the imported Blend drops from about **59.2 MB to 5.52 MB** because Blender references one topology-changing cache instead of storing 13 independent mesh objects.

### Architectural conclusion

The preferred presentation/cache architecture is now:

```text
SPlisHSPlasH
  -> VTK particle sequence
  -> pySplashSurf surface meshes
  -> direct OpenUSD authoring
       one UsdGeom.Mesh
       time-sampled points
       time-sampled faceVertexCounts
       time-sampled faceVertexIndices
  -> Blender
       one mesh object
       Mesh Sequence Cache modifier
```

This is currently the strongest reusable cache representation tested in this repo.

Keep the 13-object Blend as a regression/reference implementation, but use direct topology-varying USD as the preferred path for future SPH-to-Blender work.

Natural next test:

- render the direct-USD-backed Blender scene,
- add the dynamic rigid-body cube animation beside the fluid cache,
- verify both stay synchronized over all 13 frames,
- publish that rendered result to Pages.


## 2026-09-28 synchronized fluid + dynamic cube USD render — success

Workflow:

- `SPH fluid cube USD render`
- run: **#2**
- Actions run id: **36359942969**
- source commit: `020368bac5ed2a3d1d4a2817bea014a27b64c042`

The final cache contains two animated mesh prims:

- `/FluidSurface`
- `/DynamicCube`

Blender imported them as exactly two mesh objects. Both use
`MESH_SEQUENCE_CACHE`.

Validation:

- frames: **13**
- fluid mesh objects: **1**
- dynamic cube mesh objects: **1**
- replay errors: **0**
- fluid topology matched all 13 source frames
- cube topology stayed at **8 vertices / 12 faces**
- cube first centroid in Blender coordinates: **[-0.1, 0.0, 0.519852]**
- cube last centroid: **[1.873282, 0.024456, 0.153315]**
- actual frame 1 -> frame 13 displacement: **2.007184 m**

Artifacts:

- combined USD: **15,298,504 bytes**
- portable Blend: **5,610,696 bytes**
- preview PNG: **241,653 bytes**
- MP4: **22,971 bytes**

The result is stored under:

`results/sph-fluid-cube-usd-render/`

and is configured for the Pages gallery.

### Numeric frame sorting bug discovered

The original `dam-break-cube/validate.py` used ordinary lexicographic sorting
for files named `rb_data_1_1.vtk ... rb_data_1_13.vtk`.

That order ends with frame 9 rather than frame 13:

```text
1, 10, 11, 12, 13, 2, ... 9
```

Therefore the earlier reported displacement **1.366636 m** was actually the
frame 1 -> frame 9 displacement.

The validator now parses and sorts numeric frame suffixes. The corrected
frame 1 -> frame 13 displacement is about **2.007184 m**.


## 2026-09-28 long-duration / 5-second scale test

The next scale dimension is **time**, while keeping the original ~1800-particle
scene unchanged.

Target:

- previous baseline: about 1 second / 13 exported frames
- scale test: 5 seconds / roughly 60 exported frames at 12 fps
- keep particle count fixed so temporal scaling can be measured independently
- observe the dynamic cube after it reaches the far side of the tank

New files:

- `sph-experiments/long-duration-5s/prepare_cache.py`
- `sph-experiments/long-duration-5s/build_and_render.py`
- `.github/workflows/sph-long-duration-5s.yml`

Long-sequence pipeline:

```text
SPlisHSPlasH VTK sequence
  -> pySplashSurf per frame
  -> compressed NPZ surface sequence
       vertices: float32
       triangles: int32
  -> direct OpenUSD
       /FluidSurface
       /DynamicCube
  -> Blender Mesh Sequence Cache
  -> validate every frame
  -> render MP4
  -> Pages
```

The compressed NPZ stage intentionally replaces the earlier OBJ sequence.
OBJ was useful for the 13-frame proof of concept, but scales poorly for longer
runs because it is text-heavy and repeats large topology data verbosely.

### Long-duration failure history

#### Run #1 — Actions id 36360733632

- SPH step completed successfully.
- Post-simulation check still found only **13 frames**.
- Cause: passing `--stopAt 5.0` after the scene path did not extend the
  scene's `Configuration.stopAt: 1.0`.

#### Run #2 — Actions id 36360827839

- CLI argument order was changed to match upstream examples:
  options before the scene path.
- The command line visibly contained `--stopAt 5.0`.
- The simulator still stopped after the scene's one-second limit and emitted
  only 13 frames.
- Conclusion for this build/scene combination: do not rely on the CLI
  `--stopAt` override for the long-duration test.

#### Run #3 — Actions id 36360959609

The workflow now generates a temporary scene JSON **in the original scene
directory** and changes:

```json
"Configuration": {
  "stopAt": 5.0
}
```

Placing the generated file beside the original preserves relative model paths
such as `models/UnitBox.obj`.

Run #3 completed successfully.

Final verified result:

- exported frames: **61**
- simulated span: **5.0 s** from first to last sample
- nominal 61-frame playback length at 12 fps: **5.0833 s**
- SPH simulation wall time: **12.53 s**
- particle count: **1800**
- surface vertices per frame: **49,554 .. 59,258**
- surface faces per frame: **91,908 .. 111,316**
- compressed NPZ surfaces total: **51,406,712 bytes**
- all-frame surface reconstruction time: **13.931 s**
- direct USD authoring time: **8.100 s**
- Blender USD import time: **0.0376 s**
- headless scrub through all 61 frames: **1.306 s**
- Blender render time: **415.090 s**
- direct USD size: **70,695,428 bytes**
- portable Blend size: **5,636,876 bytes**
- preview PNG: **283,154 bytes**
- MP4: **113,836 bytes**
- fluid objects in Blender: **1**
- dynamic cube objects in Blender: **1**
- both use `MESH_SEQUENCE_CACHE`
- validation errors: **0**

Dynamic cube observations over the long run:

- path length: **2.588881 m**
- Blender-X range: **-0.1000 .. 1.98225 m**
- X-direction reversals: **2**
- minimum vertical coordinate: about **0.09614 m**
- final centroid: about **[1.86730, 0.00857, 0.12772]**

This confirms that extending the timeline exposed behavior that was not
visible in the 1-second baseline: the cube reaches the far side of the tank,
changes X direction, and later changes direction again while the fluid
continues settling.

Persistent result:

`results/sph-long-duration-5s/`

Pages deployment also completed successfully via `Pages gallery` run #6.

The temporal scale test is therefore complete.

### Frame-number sorting bug — wider scope

The earlier bug was not limited to `validate.py`.

Both of these patterns are unsafe:

```python
sorted(vtk_dir.glob("ParticleData_Fluid_*.vtk"))
sorted(vtk_dir.glob("rb_data_1_*.vtk"))
```

because lexicographic order becomes:

```text
1, 10, 11, 12, 13, 2, ... 9
```

The rigid-body validator was already fixed to parse numeric suffixes.

The one-frame `reconstruct.py` also used lexicographic sorting when choosing
`particle_files[-1]`, which meant `surface-final.obj` could represent
frame 9 rather than the true final frame 13. It has now been changed to parse
and sort numeric frame suffixes too.

Rule for all future VTK sequence code:

**Never rely on filename lexicographic order. Parse the numeric frame suffix.**

### Current preferred architecture

For short or long SPH-to-Blender work, the preferred path is now:

```text
SPlisHSPlasH
  -> VTK particles + rigid body geometry
  -> pySplashSurf
  -> compressed binary surface cache for intermediate work
  -> direct OpenUSD authoring
       one topology-varying FluidSurface
       one animated DynamicCube
  -> Blender
       two Mesh Sequence Cache objects
       materials / camera / lighting / render only
```

Keep these earlier results as regression references:

- 13-object Blender surface-sequence baseline
- direct single-fluid USD result
- synchronized fluid + dynamic cube USD result


## 2026-09-28 corrected one-second regression after numeric sorting

Workflow:

- `SPH fluid sample`
- run: **#13**
- Actions run id: **36361411160**

This rerun verifies that numeric frame sorting works in both validation and
final-surface selection.

Current corrected result:

- fluid frames: **13**
- rigid-body frames: **13**
- particles: **1800**
- frame 1 -> frame 13 cube displacement: **2.007310 m**
- true final surface vertices: **207,276**
- true final surface faces: **407,352**
- true final OBJ size: **20,799,581 bytes**

This supersedes old "final surface" numbers produced when
`reconstruct.py` accidentally treated lexicographic frame 9 as the final
frame.
