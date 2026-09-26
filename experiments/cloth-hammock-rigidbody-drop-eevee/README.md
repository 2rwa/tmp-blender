# Cloth Hammock Rigid Body Drop EEVEE

A hybrid physics experiment for the tmp-blender GitHub Actions pipeline.

The visible cloth uses Blender Cloth with self collision. Twelve real Bullet rigid-body spheres are released at staggered frames. Each sphere also carries a Cloth Collision modifier so the cloth reacts to its motion.

Blender does not provide a fully bidirectional Cloth <-> Rigid Body solver, so this experiment uses a hidden passive rigid-body proxy beneath the hammock. The Bullet spheres are supported by that proxy while their animated rigid-body motion deforms the visible cloth. This gives a stable composite simulation while keeping both systems genuinely simulated.

## Pipeline

1. advance frames sequentially so Cloth and Rigid Body simulations run together;
2. copy the visible cloth deformation into one shape key per frame;
3. bake selected rigid bodies to object keyframes;
4. save the prepared .blend;
5. render 24-frame chunks in parallel with EEVEE;
6. assemble and publish the 8-second movie.

## Profile

- 480 x 360
- 24 fps
- 192 frames / 8 seconds
- 45 x 35 cloth grid
- self collision enabled
- 12 active rigid-body spheres
- staggered release
- hidden passive rigid proxy
- wind + turbulence
- animated camera
