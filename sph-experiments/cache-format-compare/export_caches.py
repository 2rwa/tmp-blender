from __future__ import annotations

import json
import time
from pathlib import Path

import bpy


ROOT = Path.cwd()
SOURCE_BLEND = ROOT / "results" / "sph-dam-break-blender-sequence" / "surface-sequence.blend"
OUT = ROOT / "output" / "sph-cache-compare"
OUT.mkdir(parents=True, exist_ok=True)

ABC = OUT / "fluid-sequence.abc"
USDC = OUT / "fluid-sequence.usdc"
METRICS = OUT / "export-metrics.json"


def op_supported_kwargs(op, desired: dict) -> dict:
    props = {p.identifier for p in op.get_rna_type().properties}
    return {k: v for k, v in desired.items() if k in props}


def select_fluid_objects():
    bpy.ops.object.select_all(action="DESELECT")
    fluid = sorted(
        [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and obj.name.startswith("FluidFrame_")],
        key=lambda obj: obj.name,
    )
    if not fluid:
        raise RuntimeError("no FluidFrame_* mesh objects found")
    for obj in fluid:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = fluid[0]
    return fluid


scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 13
scene.render.fps = 12
scene.render.fps_base = 1.0
scene.frame_set(1)

fluid = select_fluid_objects()

baseline = {
    "source_blend": str(SOURCE_BLEND.relative_to(ROOT)),
    "source_blend_bytes": SOURCE_BLEND.stat().st_size,
    "fluid_objects": len(fluid),
    "mesh_vertices_sum": sum(len(obj.data.vertices) for obj in fluid),
    "mesh_faces_sum": sum(len(obj.data.polygons) for obj in fluid),
    "frame_start": scene.frame_start,
    "frame_end": scene.frame_end,
    "fps": scene.render.fps,
}

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
        "use_instancing": True,
        "as_background_job": False,
        "evaluation_mode": "VIEWPORT",
    },
)
t0 = time.perf_counter()
result_abc = bpy.ops.wm.alembic_export(**abc_args)
abc_seconds = time.perf_counter() - t0
if "FINISHED" not in result_abc or not ABC.is_file() or ABC.stat().st_size == 0:
    raise RuntimeError(f"Alembic export failed: {result_abc}")

# Re-select because exporters may alter selection/context.
fluid = select_fluid_objects()
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
t0 = time.perf_counter()
result_usd = bpy.ops.wm.usd_export(**usd_args)
usd_seconds = time.perf_counter() - t0
if "FINISHED" not in result_usd or not USDC.is_file() or USDC.stat().st_size == 0:
    raise RuntimeError(f"USD export failed: {result_usd}")

payload = {
    "baseline": baseline,
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
