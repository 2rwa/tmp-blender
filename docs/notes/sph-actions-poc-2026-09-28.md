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
- dynamic cube final centroid: `[1.216418, 0.153072, -0.014484]`
- dynamic cube displacement: **1.366636 m**
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

> Read `2rwa/tmp-blender/docs/notes/sph-actions-poc-2026-09-28.md` and continue the SPlisHSPlasH -> Blender cache experiment from the successful run #10.
