# Single-object topology-changing SPH cache

This experiment asks the next question after the 13-object Alembic/USD container baseline:

**Can Blender export the 13 SPH surface frames as one animated mesh object whose topology changes over time?**

The source is the already-validated `surface-sequence.blend`.

Inside Blender, the 13 mesh datablocks are copied and a single `FluidSurface` object is created. A `frame_change_pre` handler swaps that object's mesh datablock before dependency-graph evaluation on each frame. Blender's Alembic/USD exporters then sample frames 1..13.

After export, each cache is imported into a fresh Blender process and validated:

- exactly one mesh object must exist,
- vertex/face counts must match every original SPH surface frame,
- all 13 frames must scrub without errors,
- imported cache mechanism/modifiers are recorded.

This is an export-time construction test; the Python handler is not required after the cache has been written.
