# tmp-blender

Temporary Blender experiment repository driven by GitHub Actions.

This repository is structured for throwing many unrelated Blender experiments at the same reusable render/cache/publish pipeline.

## Layout

```text
experiments/
  <experiment-id>/
    experiment.json
    scene.py
    validate.py

tools/
  experiment.py

results/
  <experiment-id>/

output/

.github/workflows/
  blender-experiment.yml
```

## Adding an experiment

Create `experiments/<experiment-id>/` with:

1. `scene.py` — render into repository-root `output/`.
2. `validate.py` — inspect the real result and write `output/validation.json`.
3. `experiment.json` — declare the preview image and required outputs.

Example:

```json
{
  "id": "water-dump",
  "title": "Water Dump",
  "description": "Short water simulation/render experiment.",
  "preview_source": "poster.png",
  "required_outputs": ["water.mp4", "poster.png", "scene.blend"]
}
```

A push that changes `experiments/<id>/` automatically runs that experiment. Shared workflow/tool changes use `orbital-sculpture` as a smoke test. Manual runs can select any experiment with `workflow_dispatch`.

## Cache / artifact / Git roles

- cache: avoid repeating expensive Blender work when the same Actions run is retried
- artifact: temporary full media and `.blend` output
- Git: lightweight preview and validation under `results/<id>/`

## Current experiments

- [orbital-sculpture](experiments/orbital-sculpture/) — baseline still-image render\n- [water-dump](experiments/water-dump/) — short water-pour animation\n- [fire-column](experiments/fire-column/) — lightweight animated flame column


## GitHub Pages gallery

Public preview gallery:

- https://2rwa.github.io/tmp-blender/

The workflow regenerates both root index.html and docs/, so the gallery works with either common branch-based Pages source setting. Short MP4 outputs up to 5 MiB are copied into results/<experiment>/media.mp4; large media and .blend files stay in Actions artifacts.
