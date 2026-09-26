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

## Files

- `scripts/create_scene.py` - creates, saves, and renders the scene
- `scripts/validate_render.py` - validates `output/render.png`
- `.github/workflows/blender-render.yml` - installs Blender, renders, validates, and uploads the artifact

## Action artifact

A successful run uploads `blender-orbital-sculpture` containing:

- `render.png`
- `scene.blend`
- `validation.json`
- `blender-version.txt`

The workflow runs on pushes to `main` and can also be started manually with `workflow_dispatch`.
