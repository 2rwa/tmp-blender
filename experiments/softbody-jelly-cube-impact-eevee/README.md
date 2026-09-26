# Soft Body Jelly Cube Impact EEVEE

A Blender Soft Body experiment for the tmp-blender GitHub Actions pipeline.

A rounded translucent gel cube sits on a low plinth while a metallic sphere crosses the scene at high speed and collides with it. The soft-body result is sampled sequentially and baked into shape keys so the prepared .blend no longer depends on a live simulation during parallel frame rendering.

## What this experiment is testing

- whether Blender Soft Body is reliable in the headless Actions prepare stage;
- whether a weak Goal + edge springs can produce a recognizable jelly-like wobble;
- whether an animated Collision object can create a useful high-speed impact deformation;
- whether the deformation survives the existing prepared-blend / parallel-frame / ffmpeg movie pipeline.

The first version intentionally favors a visible, playful deformation over strict material realism.

## Pipeline

1. create a rounded cube and attach Blender Soft Body;
2. animate a metallic collision sphere through the gel;
3. advance frames 1-144 sequentially;
4. sample evaluated jelly vertices every frame;
5. bake the deformation into 144 shape keys;
6. remove the live Soft Body modifier;
7. save a prepared .blend;
8. render 24-frame chunks in parallel with EEVEE;
9. assemble and validate the 6-second MP4.

## Profile

- 480 x 360
- 24 fps
- 144 frames / 6 seconds
- rounded subdivided jelly mesh
- weak Goal springs for shape memory
- face + edge collision enabled
- animated metallic impact sphere
- animated camera
- translucent green gel material

## Validation

The validator checks the actual preview/movie dimensions, duration, prepared blend, baked shape-key count, projectile path, and measured maximum vertex displacement. A movie that renders but never deforms the jelly is treated as a failure.

## Possible next experiments

- three projectiles arriving while the previous wobble is still active;
- stacked jelly blocks;
- a jelly block placed on Cloth;
- a projectile trapped inside the gel;
- parameter sweeps for Goal strength, spring stiffness, damping, and collision speed.
