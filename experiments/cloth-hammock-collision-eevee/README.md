# Cloth Hammock Collision EEVEE

A deliberately non-trivial cloth physics experiment for the tmp-blender GitHub Actions pre-render pipeline.

The scene uses Blender Cloth physics on a 45 x 35 quad grid suspended from four corner patches. Two animated collision spheres hit the cloth from opposite sides while wind and turbulence act on it. Self collision is enabled.

## Why the physics is baked into shape keys

The movie workflow renders frame chunks in parallel. A live cloth simulation would otherwise make later chunks depend on simulation history from earlier frames.

The prepare step therefore:

1. runs the cloth simulation sequentially from frame 1 through 96;
2. samples the evaluated cloth mesh on every frame;
3. stores every simulated frame as a shape key;
4. removes the live Cloth modifier;
5. saves the resulting animation into the .blend.

Rendering can then be safely split across GitHub Actions jobs without re-running the physics.

## Profile

- EEVEE
- 480 x 360
- 24 fps
- 96 frames / 4 seconds
- cloth grid: 45 x 35
- Cloth quality: 8
- self collision: enabled
- two animated sphere colliders
- wind + turbulence
- 24-frame render chunks

This experiment intentionally prioritizes simulation complexity over minimum CPU cost.
