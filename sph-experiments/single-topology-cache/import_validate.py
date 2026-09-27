from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import bpy


ROOT = Path.cwd()
OUT = ROOT / "output" / "sph-single-topology-cache"
EXPECTED = [
    (54000, 100800),
    (59258, 111316),
    (50768, 94336),
    (49778, 92356),
    (49652, 92104),
    (49628, 92060),
    (49610, 92024),
    (49614, 92028),
    (49832, 92464),
    (50154, 93108),
    (49560, 91920),
    (49690, 92184),
    (49708, 92220),
]


def args_after_double_dash():
    if "--" not in sys.argv:
        raise SystemExit("expected FORMAT CACHE_PATH")
    return sys.argv[sys.argv.index("--") + 1 :]


args = args_after_double_dash()
if len(args) != 2:
    raise SystemExit("usage: ... -- FORMAT CACHE_PATH")
fmt, cache_arg = args
if fmt not in {"alembic", "usd"}:
    raise SystemExit(f"unsupported format: {fmt}")

cache = Path(cache_arg).resolve()
if not cache.is_file():
    raise SystemExit(f"missing cache {cache}")

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 13
scene.render.fps = 12
scene.render.fps_base = 1.0

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

t0 = time.perf_counter()
if fmt == "alembic":
    result = bpy.ops.wm.alembic_import(
        filepath=str(cache),
        set_frame_range=False,
        validate_meshes=False,
        always_add_cache_reader=False,
    )
else:
    result = bpy.ops.wm.usd_import(
        filepath=str(cache),
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

mesh_objects = [obj for obj in scene.objects if obj.type == "MESH"]
errors = []
if len(mesh_objects) != 1:
    errors.append(f"expected exactly 1 imported mesh object, got {len(mesh_objects)}")

obj = mesh_objects[0] if mesh_objects else None
observed = []
depsgraph = bpy.context.evaluated_depsgraph_get()
t0 = time.perf_counter()
for frame in range(1, 14):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    depsgraph.update()

    if obj is None:
        observed.append({"frame": frame, "vertices": None, "faces": None})
        continue

    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        got = (len(mesh.vertices), len(mesh.polygons))
    finally:
        evaluated.to_mesh_clear()

    observed.append({"frame": frame, "vertices": got[0], "faces": got[1]})
    if got != EXPECTED[frame - 1]:
        errors.append(f"frame {frame}: topology {got} != {EXPECTED[frame - 1]}")

scrub_seconds = time.perf_counter() - t0

modifiers = [m.type for m in obj.modifiers] if obj else []
constraints = [c.type for c in obj.constraints] if obj else []

blend = OUT / f"{fmt}-single-import.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend))

payload = {
    "format": fmt,
    "cache": cache.name,
    "cache_bytes": cache.stat().st_size,
    "import_seconds": import_seconds,
    "scrub_13_frames_seconds": scrub_seconds,
    "mesh_objects": len(mesh_objects),
    "modifiers": modifiers,
    "constraints": constraints,
    "errors": errors,
    "observed": observed,
    "imported_blend": blend.name,
    "imported_blend_bytes": blend.stat().st_size,
}
(OUT / f"{fmt}-validation.json").write_text(
    json.dumps(payload, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(payload, indent=2))
if errors:
    raise SystemExit(f"{fmt} validation failed")
