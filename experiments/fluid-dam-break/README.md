# Fluid Dam Break

Real Blender Mantaflow liquid simulation for the shared tmp-blender pipeline.

The experiment deliberately starts small enough for GitHub Actions:

- Blender 4.0.2
- liquid domain, FLIP method
- resolution max 32
- 42 frames at 24 fps
- Modular cache
- explicit Data bake followed by Mesh bake
- one central obstacle and one low barrier

Outputs:

- `fluid-dam-break.mp4` — rendered simulation
- `poster.png` — representative frame
- `fluid-sim.blend` — editable Mantaflow setup, saved after baking
- `fluid-result.blend` — self-contained frozen liquid mesh at the poster frame
- `fluid-cache/` — external Mantaflow cache, artifact/cache only
- `validation.json`

The two .blend files opt in to Git publication. Each is committed only when it is 10 MiB or smaller. Larger files remain in the Actions artifact, leaving Dropbox as the next long-term storage option.
