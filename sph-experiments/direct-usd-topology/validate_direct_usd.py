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


if "--" not in sys.argv:
    raise SystemExit("expected USD path after --")
args = sys.argv[sys.argv.index("--") + 1 :]
if len(args) != 1:
    raise SystemExit("usage: ... -- USD_PATH")

usd_path = Path(args[0]).resolve()
if not usd_path.is_file():
    raise SystemExit(f"missing USD: {usd_path}")

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 13
scene.render.fps = 12
scene.render.fps_base = 1.0

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

t0 = time.perf_counter()
result = bpy.ops.wm.usd_import(
    filepath=str(usd_path),
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
    raise RuntimeError(f"USD import failed: {result}")

mesh_objects = [obj for obj in scene.objects if obj.type == "MESH"]
errors = []
if len(mesh_objects) != 1:
    errors.append(f"expected 1 imported mesh object, got {len(mesh_objects)}")

obj = mesh_objects[0] if mesh_objects else None
depsgraph = bpy.context.evaluated_depsgraph_get()
observed = []

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

if obj is not None and "MESH_SEQUENCE_CACHE" not in modifiers:
    errors.append(f"expected MESH_SEQUENCE_CACHE modifier, got {modifiers}")

blend_path = OUT / "direct-usd-import.blend"
bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

payload = {
    "cache": usd_path.name,
    "cache_bytes": usd_path.stat().st_size,
    "import_seconds": import_seconds,
    "scrub_13_frames_seconds": scrub_seconds,
    "mesh_objects": len(mesh_objects),
    "modifiers": modifiers,
    "constraints": constraints,
    "errors": errors,
    "observed": observed,
    "imported_blend": blend_path.name,
    "imported_blend_bytes": blend_path.stat().st_size,
}
(OUT / "direct-usd-validation.json").write_text(
    json.dumps(payload, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(payload, indent=2))

if errors:
    raise SystemExit("direct USD topology replay validation failed")
