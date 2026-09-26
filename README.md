# tmp-blender

Temporary repository for testing Blender jobs on GitHub Actions.

## Experiment 01: orbital sculpture

The workflow builds a small procedural scene entirely from Blender Python:

- a metallic center sphere
- a tilted torus
- two animated-looking rings of small spheres
- a floor, camera, and three area lights
- a 640x640 PNG render plus the generated `.blend` file

The render is checked as an actual image, not only as a successful Blender exit. The validator checks dimensions, file size, luminance range, luminance standard deviation, and sampled color variation.

## Render / publish split

The workflow deliberately separates expensive rendering from lightweight Git publishing:

1. `render` restores an existing cache for the current Actions run when available.
2. On a cache miss it installs Blender, renders, validates, then immediately saves `output/` with `actions/cache/save`.
3. The full PNG and `.blend` file are also uploaded as a short-lived Actions artifact.
4. `publish` restores the validated cache, creates a smaller JPEG preview, rebases onto the current `main`, then commits only lightweight result files under `results/`.

This means a Git commit/push failure can be retried without paying for another Blender render. Even a full rerun of the same Actions run can reuse the saved render cache.

## Files

- `scripts/create_scene.py` - creates, saves, and renders the scene
- `scripts/validate_render.py` - validates `output/render.png`
- `scripts/make_preview.py` - creates the lightweight preview used in Git
- `.github/workflows/blender-render.yml` - render/cache/artifact/publish pipeline
- `results/` - latest lightweight render result written back by GitHub Actions

## Latest result

After a successful publish job, see [`results/README.md`](results/README.md) for the latest preview and validation values.

## Action artifact

A successful render job uploads `blender-orbital-sculpture` containing:

- `render.png`
- `scene.blend`
- `validation.json`
- `blender-version.txt`

The artifact is temporary; the preview and validation summary under `results/` are committed to Git for persistent viewing.

The workflow runs on pushes to `main` and can also be started manually with `workflow_dispatch`. Commits that only update `results/**` do not trigger another render.
