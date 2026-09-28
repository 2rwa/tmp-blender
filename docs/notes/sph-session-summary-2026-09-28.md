# SPH + Blender / Geometry Nodes knowledge summary — 2026-09-28

This note consolidates the useful findings from the 2026-09-28 SPH experiments in `2rwa/tmp-blender`.
It is intended to be read before extending the experiments.

## Current conclusion

The most useful architecture discovered today is:

```
SPlisHSPlasH 2.18.1
  -> VTK particle frames
  -> compact NPZ cache
  -> animated vertex-only USD
  -> Blender Mesh Sequence Cache
  -> Geometry Nodes
       Mesh to Points
       -> Instance on Points
       -> Realize Instances
  -> preview.png / media.mp4 / .blend / validation.json
```

For the current particle counts this is cheap enough that GitHub Actions can be used as the normal experiment loop.
The SPH solve itself is often much cheaper than the Blender render.  The lightweight Geometry Nodes point representation is therefore a good default for broad parameter sweeps; expensive volume/surface reconstruction should be reserved for cases worth promoting.

The particle data is the source of truth.  Surface meshes and rendered visuals are downstream presentations.

---

## Proven workflows

### Point-volume / point-cloud path

- workflow: `SPH Geometry Nodes point volume`
- successful run: `36367596940`
- source SHA: `040d3d6f57267785db7461a2ea9513e9faf8bf35`
- related note: `docs/notes/sph-point-cloud-geometry-nodes-2026-09-28.md`

Proven path:

```
VTK -> NPZ -> vertex-only USD -> Blender Mesh Sequence Cache -> Geometry Nodes
```

The point-volume experiment also proved that particle caches can be reused as the source for later surface reconstruction.

### Velocity / acceleration diagnostics

- workflow: `SPH point diagnostics`
- successful run: `36369860412`
- source SHA: `49feb3b91b96b85c74e5a80ffd3c392f33ce2090`

Modes:

- velocity arrows
- acceleration color bands
- combined acceleration colors + sparse velocity arrows

The successful reference solve was 61 frames / 1800 particles / 12 fps.
Velocity p95 was about 2.446 and acceleration p97 about 16.81.

Important failure:
the first diagnostics run produced instance-based Geometry Nodes output.  `evaluated.to_mesh()` therefore saw empty geometry.
Fix: insert `GeometryNodeRealizeInstances` before Group Output.

This node should remain in validation-oriented Geometry Nodes graphs.

---

## Five basic SPH samples

Directory:

- `sph-experiments/sample-pack/`

Workflow:

- `SPH sample pack 5`
- run `36374953517`
- conclusion: success
- source SHA: `adfca2179627f6e1c912549c7ee5a3d1e7f046d9`

Cases:

1. `dam-break`
2. `tall-column`
3. `falling-slug`
4. `two-towers`
5. `tilted-surge`

First-pass preset:

- stopAt: 2 s
- output: 12 fps / 25 frames
- particle radius: 0.07
- render: 640x360
- five-way matrix parallelism
- persistent Git write only in one publish job

This was fast enough that five small experiments can be treated as a normal exploratory unit rather than a costly batch.

---

## Two-fluid / two-phase SPH

Directory:

- `sph-experiments/two-phase-pack/`

Workflow:

- `SPH two-phase sample pack 5`
- final successful run: `36377544339`
- source SHA: `6f5880855d929f17d1ab1e908cb1825a1d4551fc`

SPlisHSPlasH supports distinct fluid models by matching:

```
FluidBlock.id -> Materials.id
```

The VTK exporter preserves them as distinct streams:

```
ParticleData_PhaseA_<frame>.vtk
ParticleData_PhaseB_<frame>.vtk
```

This means the blue/orange display is not only cosmetic: PhaseA and PhaseB are separate SPlisHSPlasH fluid models with their own density and viscosity.

Cases:

1. `stratified-oil-water`
2. `dual-dam-break`
3. `heavy-drop-into-light-pool`
4. `light-drop-into-heavy-pool`
5. `opposed-two-phase-jets`

All five completed with `errors: []`.

Examples from persisted validation:

| case | particles | Blender render |
|---|---:|---:|
| stratified-oil-water | 1320 | ~101.8 s |
| dual-dam-break | 1134 | ~98.3 s |
| heavy-drop-into-light-pool | 586 | ~70.0 s |
| light-drop-into-heavy-pool | 586 | ~58.6 s |
| opposed-two-phase-jets | 90 | ~53.8 s |

The heavy/light drop experiments show the falling phase centroid moving roughly 1.2 m over the sequence.
The two-fluid streams remain separately renderable throughout the pipeline.

### Two-phase failures worth remembering

Run #1: `36376576074`

The SPH solve succeeded and both phases produced 25 VTK frames, but the cache builder failed because the frame-number regex was accidentally double escaped.

Bad:

```python
r"_(\\d+)\\.vtk$"
```

Correct:

```python
r"_(\d+)\.vtk$"
```

Run #2: `36377159700`

SPH, NPZ, USD, Geometry Nodes, preview, video and validation all succeeded.
Actions still reported failure because a shell `grep` used over-escaped square brackets while checking `"errors": []`.

Fix: parse the JSON instead of validating JSON syntax with grep.

```bash
python -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["errors"] == [], d["errors"]' validation.json
```

Run #3 then succeeded.

### Next two-phase scale-up

User decision: when two-phase is revisited, increase both duration and resolution.

A reasonable next probe:

- duration: 2 s -> 4 s
- particle radius: 0.07 -> 0.05 to 0.055
- fps: keep 12 initially
- render resolution: keep 640x360 until performance is measured
- keep sample timeout at 30 minutes

Current evidence suggests the Blender point render, not the SPH solve, will be the first meaningful cost increase.

---

## Elastic SPH

Directory:

- `sph-experiments/elastic-pack/`

Workflow:

- `SPH elastic sample pack 5`
- successful run: `36381274836`
- source SHA: `2fb51eab9713e2e4d18bfefe38326f97946d5b96`
- persistent results commit: `5646f9f83949a2fd3889992deb1baab51bc83315`

SPlisHSPlasH 2.18.1 has usable elasticity examples for:

- `elasticityMethod: 2` — Peer et al. 2018
- `elasticityMethod: 3` — Kugelstadt et al. 2021

Kugelstadt also supports a fixed spatial region through `fixedBoxMin` / `fixedBoxMax`, which is useful for beams and columns.

Cases:

1. `peer-soft-cube-drop`
2. `kugelstadt-stiff-cube-drop`
3. `cantilever-beam`
4. `fixed-column-kick`
5. `elastic-block-collision`

Preset:

- particle radius: 0.04
- 2 s
- 12 fps / 25 frames
- 640x360
- point radius in Blender: 0.034

All five completed with `errors: []`.

Persisted validation:

| case | particles | render | notable final extent ratio |
|---|---:|---:|---|
| Peer soft cube drop | 1000 | ~52.9 s | x/z ~1.059, y ~0.961 |
| Kugelstadt stiff cube drop | 1000 | ~71.5 s | x/z ~1.008, y ~0.999 |
| cantilever beam | 585 | ~59.1 s | vertical extent ~8.52x |
| fixed column kick | 720 | ~65.9 s | lateral extent ~1.47x |
| elastic block collision | 1458 | ~87.1 s | longitudinal extent ~1.28x |

The soft/stiff cube pair demonstrates that the material parameter difference is visible in the particle geometry: the soft case ends noticeably wider/flatter, while the stiff case stays near its initial dimensions.
The cantilever and fixed-column experiments confirm that fixed spatial regions work for qualitative bending tests.

---

## About "bursting" elastic bodies

Important distinction:

### Easy with the current elasticity models

- strong compression
- bounce / recoil
- large deformation
- oscillation
- high-speed impact
- visually explosive rebound

These can be explored by increasing initial velocity, lowering or raising Young's modulus, changing gravity, or creating stronger impacts.

### Not currently proven

- true tearing
- fracture
- material damage
- topology breaking
- fragments becoming independent because bonds failed

The current elastic SPH setup is fundamentally a deformation / recovery model.  Do not call a large rebound "fracture".

Possible next directions:

1. **high-energy elastic rebound pack**
   - high-speed floor impact
   - high-speed head-on collision
   - hard vs soft impact comparison
   - strong cantilever kick
   - compression/release

2. **pseudo-burst**
   - construct several initially adjacent elastic blocks
   - arrange them to look like one body
   - impact or release them so they separate
   - useful visually, but document that it is not fracture

3. **true fracture research**
   - search for SPH damage/fracture methods or another solver
   - identify whether SPlisHSPlasH has an appropriate extension before implementing

4. **elastic shell + fluid**
   - potentially interesting for a bag/slime-ball/burst visual
   - coupling and actual shell failure are separate problems and should not be conflated

Recommended immediate next experiment: a five-case **high-energy / burst-like elastic pack** first, because it reuses the proven pipeline and can establish the visual limits of the existing elasticity solver before investing in fracture models.

---

## Geometry Nodes lessons

Reliable validation-oriented chain:

```
Mesh Sequence Cache
 -> Mesh to Points
 -> Instance on Points
 -> Realize Instances
```

Benefits:

- cheap
- easy to color by phase/case
- stable enough for automatic geometry validation
- reusable for velocity/acceleration diagnostics
- .blend remains useful for later inspection

Do not require surface reconstruction for every exploratory run.

For more realistic water surfaces, promote selected particle runs to:

```
Mesh to Points
 -> Points to Volume
 -> Volume to Mesh
```

rather than rerunning the SPH solve.

---

## GitHub Actions operating pattern

Current experimental workflows use:

- runtime job: 30 min timeout
- sample matrix jobs: 30 min timeout each
- publish job: 10 min timeout
- max parallel samples: usually 5

Use one persistent publish writer after the matrix to avoid concurrent push conflicts.

Recommended writer pattern:

```
fetch/rebase latest main
generate persistent result metadata
git add
commit
push
retry after fetch/rebase if necessary
```

The public repo is intentionally being used as inexpensive remote compute / rendering infrastructure.

When a user says `エラッタ`, `状況どうかな`, or says that an Actions notification arrived, inspect the workflow run and logs directly.  Do not ask the user to paste the error unless the connector cannot retrieve it.

---

## Pages / gallery

Public gallery:

https://2rwa.github.io/tmp-blender/

The gallery is generated by:

- `.github/workflows/pages-gallery.yml`
- `tools/build_pages.py`

Results live under `results/<experiment>/`.
Newest results are sorted first using the latest Git commit timestamp touching the result directory.

The gallery uses a preview image and loads the movie on click to avoid a page full of eagerly loaded videos.

---

## Relevant files

Existing broader notes:

- `docs/notes/sph-actions-poc-2026-09-28.md`
- `docs/notes/sph-point-cloud-geometry-nodes-2026-09-28.md`
- `docs/notes/START-HERE.md`

Current reusable experiment packs:

- `sph-experiments/sample-pack/`
- `sph-experiments/two-phase-pack/`
- `sph-experiments/elastic-pack/`
- `sph-experiments/point-diagnostics/`
- `sph-experiments/geometry-nodes-points-volume/`

Workflows:

- `.github/workflows/sph-sample-pack.yml`
- `.github/workflows/sph-two-phase-pack.yml`
- `.github/workflows/sph-elastic-pack.yml`
- `.github/workflows/sph-point-diagnostics.yml`
- `.github/workflows/sph-geometry-nodes-points-volume.yml`

---

## Next-session priorities

1. Read `HANDOFF_SPH_20260928.md`.
2. If continuing elasticity, test high-energy / burst-like behavior before attempting true fracture.
3. If returning to two-phase SPH, use 4 s and particle radius about 0.05-0.055 as the next scale probe.
4. Continue using lightweight Geometry Nodes point rendering for broad experiments.
5. Only promote interesting runs to volume/surface reconstruction.
