# Cloth Hammock Collision Movie EEVEE

An 8-second movie-oriented extension of the successful cloth hammock test.

The simulation architecture is unchanged: Blender Cloth is evaluated sequentially in the prepare job, every simulated frame is copied into a shape key, the live Cloth modifier is removed, and the baked .blend is then safe to render in independent frame chunks.

## Movie changes

- 192 frames / 8 seconds at 24 fps
- two separate impact phases from the animated collision spheres
- wind direction changes during the shot
- the turbulence effector moves around the cloth
- slow camera dolly/orbit with lens changes
- EEVEE rendering in 24-frame chunks

The goal is to turn the successful physics test into a short presentation clip without changing the proven simulation pipeline.

## Next experiment

The natural follow-up is a cloth + rigid-body hybrid where moving rigid bodies are simulated rather than manually animated.
