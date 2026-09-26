# tmp-blender Architecture

Updated: 2026-09-26

## Purpose

`tmp-blender` is a disposable public test repository for Blender experiments. It is optimized for fast experimentation rather than long-term repository cleanliness.

Useful experiments, scripts, and assets may later be copied into dedicated repositories. The repository itself may eventually be rewritten, cleaned, archived, or discarded.

## Repository layout

```text
experiments/
  <experiment-id>/
    experiment.json
    scene.py
    validate.py
    README.md

tools/
  experiment.py
  build_pages.py

results/
  <experiment-id>/
    README.md
    preview.jpg
    validation.json
    blender-version.txt
    media.mp4        # when small enough for Pages
    *.blend          # experiments that opt in with repo_blends

output/
  ...                # ephemeral Actions working directory

docs/
  index.html
  assets/
  notes/

.github/workflows/
  blender-experiment.yml
```

## Experiment contract

Each experiment is self-contained under `experiments/<id>/`.

`experiment.json` declares:

- `id`
- human-readable `title`
- `description`
- `preview_source`
- `required_outputs`
- optional `repo_blends`

`scene.py` creates the scene, performs simulation/baking when required, renders outputs into repository-root `output/`, and saves one or more `.blend` files.

`validate.py` inspects the real output. Validation is deliberately separate from rendering so validator mistakes can be fixed without forcing expensive work to be repeated when a render checkpoint exists.

## Actions pipeline

The workflow is split into four stages.

### 1. discover

Changed experiment folders are detected from the Git diff. Only affected experiments are selected. Shared workflow/tool changes use `orbital-sculpture` as a smoke test when no experiment was directly changed.

Python files are compiled before expensive work to catch syntax errors early.

### 2. render

The render job:

1. performs a cheap Python preflight,
2. computes a content-based render cache key,
3. restores a previous render checkpoint when possible,
4. restores the shared portable Blender runtime,
5. verifies Blender under Xvfb,
6. runs `scene.py`,
7. saves the raw render checkpoint before validation,
8. runs `validate.py`,
9. saves validated output,
10. uploads the full output as an Actions artifact.

The portable runtime currently targets Blender 4.0.2 on Linux x64.

Render cache keys intentionally ignore:

- `validate.py`
- `README.md`
- `experiment.json`
- `*.pyc`
- `__pycache__`

This allows validator/documentation fixes to reuse the expensive render when render inputs did not change.

### 3. publish

Validated output is converted into a persistent result under `results/<id>/`.

Persistent results contain a compressed preview, validation metadata, Blender version, optional small MP4 media for Pages, and selected `.blend` files.

Selected `.blend` files are published directly to Git up to a 95 MiB per-file safety threshold. The repository is intentionally disposable, so repository growth is not treated as an optimization target during experimentation.

### 4. Pages

`tools/build_pages.py` builds both root `index.html` and `docs/index.html`.

The Pages gallery includes:

- preview image or directly playable MP4,
- validation summary,
- source/result links,
- links to committed `.blend` files,
- Actions run link.

The workflow also deploys `docs/` using the official GitHub Pages Actions deployment.

Public gallery:

https://2rwa.github.io/tmp-blender/

## Storage roles

Git, Actions cache, and Actions artifacts intentionally have different roles.

| Storage | Role |
| --- | --- |
| Git | Persistent experiment source and useful generated results |
| Actions cache | Expensive intermediate/render checkpoints |
| Actions artifact | Full temporary output, including large caches and files |
| GitHub Pages | Human inspection of previews, validation, and small video |
| Dropbox (future option) | Large outputs worth retaining outside Git |

Mantaflow simulation caches, for example, stay outside Git even when the resulting `.blend` files are committed.

## Licensing

Unless otherwise noted:

- code/workflows/HTML: MIT-0
- generated `.blend`, images, video, and generated assets: CC0-1.0
- third-party source data/assets remain under their original license and terms

See `LICENSE` and `LICENSES/`.
