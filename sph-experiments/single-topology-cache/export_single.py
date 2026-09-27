from __future__ import annotations

import json
import time
from pathlib import Path

import bpy


ROOT = Path.cwd()
SOURCE = ROOT / "results" / "sph-dam-break-blender-sequence" / "surface-sequence.blend"
OUT = ROOT / "output" / "sph-single-topology-cache"
OUT.mkdir(parents=True, exist_ok=True)
ABC = OUT / "fluid-single.abc"
USDC = OUT / "fluid-single.usdc"
METRICS = OUT / "export-metrics.json"

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


def op_supported_kwargs(op, desired: dict) -> dict:
    props = {p.identifier for p in op.get_rna_type().properties}
    return {k: v for k, v in desired.items() if k in props}


scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 13
scene.render.fps = 12
scene.render.fps_base = 1.0

source_objects = sorted(
    [
        obj
        for obj in scene.objects
        if obj.type == "MESH" and obj.name.startswith("FluidFrame_")
    ],
    key=lambda obj: obj.name,
)
if len(source_objects) != 13:
    raise RuntimeError(f"expected 13 source meshes, got {len(source_objects)}")

source_meshes = []
for idx, obj in enumerate(source_objects, start=1):
    mesh = obj.data.copy()
    mesh.name = f"FluidTopo_{idx:04d}"
    got = (len(mesh.vertices), len(mesh.polygons))
    if got != EXPECTED[idx - 1]:
        raise RuntimeError(f"source frame {idx} topology mismatch: {got} != {EXPECTED[idx - 1]}")
    source_meshes.append(mesh)

# Remove all objects from the scene. The copied mesh datablocks remain available.
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

target = bpy.data.objects.new("FluidSurface", source_meshes[0])
bpy.context.collection.objects.link(target)
target.select_set(True)
bpy.context.view_layer.objects.active = target


def swap_mesh(scene_arg):
    frame = max(1, min(13, int(scene_arg.frame_current)))
    target.data = source_meshes[frame - 1]


bpy.app.handlers.frame_change_pre.append(swap_mesh)
scene.frame_set(1)
swap_mesh(scene)

# Prove that the handler exposes the expected varying topology before export.
preflight = []
for frame in range(1, 14):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    got = (len(target.data.vertices), len(target.data.polygons))
    preflight.append({"frame": frame, "vertices": got[0], "faces": got[1]})
    if got != EXPECTED[frame - 1]:
        raise RuntimeError(f"handler topology mismatch at frame {frame}: {got}")

abc_args = op_supported_kwargs(
    bpy.ops.wm.alembic_export,
    {
        "filepath": str(ABC),
        "start": 1,
        "end": 13,
        "xsamples": 1,
        "gsamples": 1,
        "selected": True,
        "visible_objects_only": False,
        "flatten": False,
        "uvs": False,
        "normals": False,
        "orcos": False,
        "face_sets": False,
        "export_hair": False,
        "export_particles": False,
        "export_custom_properties": False,
        "use_instancing": False,
        "as_background_job": False,
        "evaluation_mode": "VIEWPORT",
    },
)
scene.frame_set(1)
t0 = time.perf_counter()
result_abc = bpy.ops.wm.alembic_export(**abc_args)
abc_seconds = time.perf_counter() - t0
if "FINISHED" not in result_abc or not ABC.is_file() or ABC.stat().st_size == 0:
    raise RuntimeError(f"Alembic export failed: {result_abc}")

usd_args = op_supported_kwargs(
    bpy.ops.wm.usd_export,
    {
        "filepath": str(USDC),
        "selected_objects_only": True,
        "visible_objects_only": False,
        "export_animation": True,
        "export_hair": False,
        "export_uvmaps": False,
        "export_normals": False,
        "export_materials": False,
        "export_mesh_colors": False,
        "evaluation_mode": "VIEWPORT",
    },
)
scene.frame_set(1)
t0 = time.perf_counter()
result_usd = bpy.ops.wm.usd_export(**usd_args)
usd_seconds = time.perf_counter() - t0
if "FINISHED" not in result_usd or not USDC.is_file() or USDC.stat().st_size == 0:
    raise RuntimeError(f"USD export failed: {result_usd}")

bpy.app.handlers.frame_change_pre.remove(swap_mesh)

payload = {
    "source_blend_bytes": SOURCE.stat().st_size,
    "source_objects": 13,
    "target_objects": 1,
    "preflight": preflight,
    "alembic": {
        "path": ABC.name,
        "bytes": ABC.stat().st_size,
        "export_seconds": abc_seconds,
        "operator_args": abc_args,
    },
    "usd": {
        "path": USDC.name,
        "bytes": USDC.stat().st_size,
        "export_seconds": usd_seconds,
        "operator_args": usd_args,
    },
}
METRICS.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2))
