# SPH project handoff — 2026-09-28

This is the restart file for the next ChatGPT conversation working on `2rwa/tmp-blender`.

## Read first

1. `docs/notes/sph-session-summary-2026-09-28.md`
2. `docs/notes/sph-point-cloud-geometry-nodes-2026-09-28.md`
3. `docs/notes/sph-actions-poc-2026-09-28.md`
4. `2rwa/chatgpt-workspace/docs/build-test-fix.md` when doing implementation work

Do not infer GitHub capability from generic connector assumptions.  Inspect the GitHub tools actually exposed in the session.  Previous sessions successfully committed through the Git Data path `create_blob -> create_tree -> create_commit -> update_ref`.

## Current state

The following experiment families are already implemented, run successfully, published to `results/`, and available through the Pages gallery.

### Basic five-case SPH pack

- source: `sph-experiments/sample-pack/`
- workflow: `.github/workflows/sph-sample-pack.yml`
- successful run: `36374953517`
- cases: dam break, tall column, falling slug, twin columns, tilted surge

### Two-phase five-case pack

- source: `sph-experiments/two-phase-pack/`
- workflow: `.github/workflows/sph-two-phase-pack.yml`
- successful run: `36377544339`
- cases:
  - stratified-oil-water
  - dual-dam-break
  - heavy-drop-into-light-pool
  - light-drop-into-heavy-pool
  - opposed-two-phase-jets

Two-phase is real separate-fluid-model SPH:
`FluidBlock.id` is mapped to `Materials.id`, and SPlisHSPlasH exports separate `ParticleData_PhaseA_*` / `ParticleData_PhaseB_*` streams.

When two-phase is revisited, the user wants to scale it up:
- 4 s instead of 2 s
- particle radius roughly 0.05-0.055 instead of 0.07
- measure before increasing render resolution

### Elastic five-case pack

- source: `sph-experiments/elastic-pack/`
- workflow: `.github/workflows/sph-elastic-pack.yml`
- successful run: `36381274836`
- source SHA: `2fb51eab9713e2e4d18bfefe38326f97946d5b96`
- publish commit: `5646f9f83949a2fd3889992deb1baab51bc83315`

Cases:
- peer-soft-cube-drop
- kugelstadt-stiff-cube-drop
- cantilever-beam
- fixed-column-kick
- elastic-block-collision

All five have `errors: []`.
Typical Blender point-render time is about 53-87 seconds for 585-1458 particles and 25 frames.

SPlisHSPlasH 2.18.1 elasticity methods already proven here:
- method 2: Peer et al. 2018
- method 3: Kugelstadt et al. 2021
- Kugelstadt `fixedBoxMin/fixedBoxMax` works for fixed beam/column regions

## Current question / likely next experiment

The last discussion was: **can an elastic SPH body "burst"?**

Use this distinction:

- strong deformation / bounce / recoil / oscillation / visually explosive rebound: feasible now
- actual tearing / fracture / topology breaking / independent fragments from failed bonds: not yet proven by the current setup

The recommended next step is therefore a **five-case high-energy / burst-like elastic experiment pack** using the existing elastic pipeline before researching or implementing true fracture.

Good candidate cases:

1. high-speed soft cube floor impact
2. high-speed stiff cube floor impact
3. high-speed elastic block head-on collision
4. strongly kicked fixed column / cantilever
5. pseudo-burst using several adjacent elastic blocks, clearly labelled as not true fracture

If the user instead explicitly asks for real fracture, first research suitable SPH damage/fracture support rather than pretending the current elasticity model tears.

## Reusable architecture

Default broad-test path:

```
SPlisHSPlasH 2.18.1
 -> VTK
 -> NPZ
 -> animated vertex-only USD
 -> Blender Mesh Sequence Cache
 -> Geometry Nodes:
      Mesh to Points
      -> Instance on Points
      -> Realize Instances
 -> preview + mp4 + blend + validation
```

Keep `Realize Instances` before output when validating evaluated geometry.

Use the particle cache as source-of-truth.  For an interesting run, surface reconstruction can be added later with `Points to Volume -> Volume to Mesh` without rerunning the physics.

## Actions conventions

Current timeout settings:
- runtime: 30 min
- each sample matrix job: 30 min
- publish: 10 min

Five-case matrices are normal and have been cheap enough to run aggressively.

Persistent result writes should happen in one publish job after matrix completion.
Pages gallery is refreshed through `.github/workflows/pages-gallery.yml`.

When the user says `エラッタ` or reports an Actions notification, inspect the run/jobs/logs directly, diagnose, commit the fix, and relaunch without asking the user to paste logs.

Known mistakes already fixed:
- double-escaped VTK frame regex
- using shell grep to validate JSON `errors: []`
- forgetting `Realize Instances` before geometry validation

## User preference for this project

Prefer experiment-first iteration.  Failures are useful data.
Do not stop merely because a test might fail.
Use Actions for long/parallel work and return after immediate failures have been checked.
Document useful failures and successful architecture so the next conversation can restart from GitHub rather than chat history.

## Public output

Gallery:
https://2rwa.github.io/tmp-blender/

Primary consolidated note:
`docs/notes/sph-session-summary-2026-09-28.md`
