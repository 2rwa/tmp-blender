# Metaball Hidden Funnel 300 EEVEE

A deliberately aggressive Blender physics experiment.

## Idea

Three hundred particles appear to fall freely, mysteriously converge, pass through a narrow invisible path, and emerge above a visible receiving dish.

The trick is split into two layers:

- **physics:** 300 small rigid-body proxy spheres;
- **appearance:** 300 metaball elements driven by the sampled rigid-body positions.

The funnel and tube are passive rigid-body mesh colliders with `hide_render=True`. After the simulation is sampled, all proxy bodies and hidden colliders are removed from the prepared render scene, leaving only the metaball animation and visible receiver.

## Pipeline

1. Create invisible open frustum funnel and open tube as passive Bullet mesh colliders.
2. Create 300 low-poly rigid-body spheres sharing one mesh.
3. Stagger their kinematic release over the first 84 frames.
4. Evaluate Bullet sequentially for 192 frames.
5. Sample every proxy position.
6. Bake those positions into 300 metaball elements.
7. Remove all physics helpers.
8. Save prepared Blend.
9. Render eight 24-frame chunks in parallel.
10. Assemble and validate the 8-second MP4.

## Why this is allowed to fail

This experiment is intentionally probing:

- whether open passive mesh colliders behave reliably headlessly;
- whether 300 rigid bodies funnel through a narrow tube without catastrophic tunneling;
- whether the metaball surface turns the hidden collision path into a convincing liquid-like stream;
- where the CPU cost moves when real Bullet collision replaces analytic trajectories.

The validator is intentionally permissive: it only requires a meaningful fraction of the 300 bodies to exit the hidden tube and reach the receiver. A partial jam is useful experimental data rather than an automatic design failure.
