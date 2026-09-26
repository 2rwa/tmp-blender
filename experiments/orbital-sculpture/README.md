# Orbital Sculpture

Baseline image-render experiment used to verify the shared tmp-blender pipeline.

## Contract

- `scene.py` renders into repository-root `output/`.
- `validate.py` validates the real render and writes `output/validation.json`.
- `experiment.json` declares preview and required outputs.
- the shared workflow caches `output/`, uploads the full artifact, and commits a lightweight preview under `results/orbital-sculpture/`.

Expected full outputs:

- `render.png`
- `scene.blend`
- `validation.json`
- `blender-version.txt`
