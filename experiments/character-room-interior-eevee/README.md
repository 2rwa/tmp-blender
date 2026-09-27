# Character Room Interior EEVEE

A reusable room-scale environment test built on the working character/Actions pipeline.

## Scene

- room: 7.2 m x 5.4 m x 3.0 m
- presentation: open front so the camera can inspect the entire interior
- window opening in the back wall
- side door panel / frame
- rug
- sofa
- coffee table
- desk + monitor + keyboard
- chair
- bookshelf
- floor lamp
- ceiling panel
- wall art
- four-light setup
- Quaternius Warrior normalized to about 1.78 m and playing an idle action

Everything except the character is generated from Blender primitives by `scene.py`.

## Movie

- EEVEE
- 480 x 360
- 24 fps
- 360 frames / 15 seconds
- four camera keyframes
- 60-frame render chunks

This is a measured environment scaffold that can later receive multiple animated characters, rigid bodies, cloth, interaction props, or heavier lighting.

## Validation

The report checks exact room dimensions, shell/furniture/decor counts, light count, camera keyframes, overall mesh count, character source/rig/actions, human-scale height, and the complete 15-second movie.

The character acquisition path is the same verified Quaternius CC0 mirror used by the earlier successful character tests.
