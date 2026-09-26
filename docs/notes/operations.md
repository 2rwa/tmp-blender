# Operating Notes

Updated: 2026-09-26

## Long-running Actions rule

Do not keep the conversation blocked while a render, bake, simulation, or other long task is running.

Recommended pattern:

1. push the experiment,
2. check discovery/preflight,
3. watch for immediate Blender/Python/API failures,
4. if the job has entered genuine long-running work, return the conversation turn,
5. check the run again on the next user turn.

This is especially important for Mantaflow, large rigid-body scenes, animation rendering, and other tasks likely to exceed roughly 30 seconds.

## Failure-handling rule

Failures should be classified by stage.

### Preflight / setup failure

Examples:

- Python syntax error
- invalid manifest
- missing Blender property
- missing runtime dependency

Fix immediately. No expensive work has been lost.

### Blender build/render failure

Inspect `output/blender-scene.log`. The workflow treats a Python traceback as failure even when Blender itself exits with status 0.

When possible, correct only the scene input that caused the failure.

### Validation failure after successful render

Do not rerender automatically just because validation logic was wrong.

The raw render checkpoint is intentionally saved before validation. Change only `validate.py` where possible; because validator files are excluded from the render hash, the next run should be able to reuse the checkpoint.

### Publish/Pages failure

Do not rerender. The validated output is already cached/artifacted. Fix the publish or Pages tooling separately.

## Blender runtime notes

Current target:

```text
Blender 4.0.2
Linux x64
Xvfb
LIBGL_ALWAYS_SOFTWARE=1
SDL_AUDIODRIVER=dummy
```

Portable Blender requires Xvfb in the Actions environment. Direct headless execution previously failed because of EGL/GL context initialization.

Do not assume property names from a different Blender release.

Known Blender 4.0.2 examples from this repository:

- Ocean modifier uses `wave_scale_min`, not `smallest_wave`
- RigidBodyWorld uses `substeps_per_frame`, not `steps_per_second`

## Result publication

Experiments opt into committed Blender files with:

```json
"repo_blends": [
  "example-sim.blend",
  "example-result.blend"
]
```

Current policy:

- selected `.blend` files below 95 MiB: commit to Git
- small MP4s below 5 MiB: copy to `results/<id>/media.mp4` for Pages
- large simulation caches/intermediates: Actions cache/artifact
- large persistent outputs worth keeping later: Dropbox is an available future option

The current conversation intentionally does not optimize repository size.

## Temporary-repository philosophy

`tmp-blender` is not a preservation repository.

It is acceptable to:

- accumulate binary history,
- keep redundant test results,
- try expensive Blender features,
- commit useful binary results directly,
- later copy successful experiments into dedicated repositories,
- eventually rewrite history or delete the repository.

A separate local maintenance/cleanup batch should handle repository cleanup rather than making every experiment storage-aware.

## Licensing rule

Default:

- code, scripts, workflows, HTML: MIT-0
- generated Blender files/renders/video/assets: CC0-1.0
- third-party material: original source license/terms apply

New experiments should include the bilingual license notice in their README. Generated result READMEs receive the same notice automatically from `tools/experiment.py`.

## Adding a new experiment

Minimum files:

```text
experiments/<id>/
  experiment.json
  scene.py
  validate.py
  README.md
```

Before pushing:

- ensure Python compiles,
- keep all generated paths under repository-root `output/`,
- declare every required output in the manifest,
- use `repo_blends` for Blender files that should be published,
- make validators check useful properties rather than arbitrary file-size thresholds,
- prefer representative visual checks over brittle assumptions.

## Pages notes

`docs/assets/` is regenerated from `results/`.

Persistent engineering notes therefore live under `docs/notes/`, which is not deleted by `tools/build_pages.py`.

The current public gallery is:

https://2rwa.github.io/tmp-blender/
