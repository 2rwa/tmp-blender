from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import bpy


ROOT = Path.cwd()
OUT = ROOT / "output" / "sph-cache-compare"


def args_after_double_dash():
    if "--" not in sys.argv:
        raise SystemExit("expected arguments after --: FORMAT CACHE_PATH")
    return sys.argv[sys.argv.index("--") + 1 :]


args = args_after_double_dash()
if len(args) != 2:
    raise SystemExit("usage: blender ... --python import_validate.py -- FORMAT CACHE_PATH")

fmt, cache_arg = args
if fmt not in {"alembic", "usd"}:
    raise SystemExit(f"unsupported format: {fmt}")

cache_path = Path(cache_arg).resolve()
if not cache_path.is_file():
    raise SystemExit(f"missing cache: {cache_path}")

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 13
scene.render.fps = 12
scene.render.fps_base = 1.0
scene.frame_set(1)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

t0 = time.perf_counter()
if fmt == "alembic":
    result = bpy.ops.wm.alembic_import(
        filepath=str(cache_path),
        set_frame_range=False,
        validate_meshes=False,
        always_add_cache_reader=False,
    )
else:
    result = bpy.ops.wm.usd_import(
        filepath=str(cache_path),
        set_frame_range=False,
        import_cameras=False,
        import_curves=False,
        import_lights=False,
        import_materials=False,
        import_meshes=True,
        import_volumes=False,
    )
import_seconds = time.perf_counter() - t0
if "FINISHED" not in result:
    raise RuntimeError(f"{fmt} import failed: {result}")

mesh_objects = sorted(
    [obj for obj in scene.objects if obj.type == "MESH"],
    key=lambda obj: obj.name,
)
if len(mesh_objects) != 13:
    print(f"WARNING imported mesh object count={len(mesh_objects)} expected=13")

depsgraph = bpy.context.evaluated_depsgraph_get()
observed = []
errors = []
scrub_t0 = time.perf_counter()

for frame in range(1, 14):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    depsgraph.update()

    visible = []
    for obj in mesh_objects:
        evaluated = obj.evaluated_get(depsgraph)
        scale = evaluated.matrix_world.to_scale()
        if max(abs(scale.x), abs(scale.y), abs(scale.z)) > 0.5:
            visible.append(obj)

    record = {
        "frame": frame,
        "visible_count": len(visible),
        "visible": [obj.name for obj in visible],
    }
    if len(visible) == 1:
        evaluated = visible[0].evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            record["vertices"] = len(mesh.vertices)
            record["faces"] = len(mesh.polygons)
        finally:
            evaluated.to_mesh_clear()
    else:
        errors.append(
            f"frame {frame}: expected 1 visible fluid mesh, got {len(visible)} "
            f"{[obj.name for obj in visible]}"
        )
    observed.append(record)

scrub_seconds = time.perf_counter() - scrub_t0

constraints = {}
modifiers = {}
for obj in mesh_objects:
    constraints[obj.name] = [c.type for c in obj.constraints]
    modifiers[obj.name] = [m.type for m in obj.modifiers]

imported_blend = OUT / f"{fmt}-import.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(imported_blend))

payload = {
    "format": fmt,
    "cache_path": cache_path.name,
    "cache_bytes": cache_path.stat().st_size,
    "import_seconds": import_seconds,
    "scrub_13_frames_seconds": scrub_seconds,
    "mesh_objects": len(mesh_objects),
    "constraints": constraints,
    "modifiers": modifiers,
    "errors": errors,
    "observed": observed,
    "imported_blend": imported_blend.name,
    "imported_blend_bytes": imported_blend.stat().st_size,
}
path = OUT / f"{fmt}-validation.json"
path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2))
if errors:
    raise SystemExit(f"{fmt} timeline replay validation failed")
