from __future__ import annotations

import json
import time
from pathlib import Path

import bpy
from pxr import Gf, Usd, UsdGeom, Vt


ROOT = Path.cwd()
SOURCE = ROOT / "results" / "sph-dam-break-blender-sequence" / "surface-sequence.blend"
OUT = ROOT / "output" / "sph-single-topology-cache"
OUT.mkdir(parents=True, exist_ok=True)

USD_PATH = OUT / "fluid-direct-single.usdc"
METRICS_PATH = OUT / "direct-usd-export.json"


scene = bpy.context.scene
source_objects = sorted(
    [
        obj
        for obj in scene.objects
        if obj.type == "MESH" and obj.name.startswith("FluidFrame_")
    ],
    key=lambda obj: obj.name,
)
if len(source_objects) != 13:
    raise RuntimeError(f"expected 13 source fluid meshes, got {len(source_objects)}")

stage = Usd.Stage.CreateNew(str(USD_PATH))
stage.SetStartTimeCode(1)
stage.SetEndTimeCode(13)
stage.SetFramesPerSecond(12)
stage.SetTimeCodesPerSecond(12)
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

mesh = UsdGeom.Mesh.Define(stage, "/FluidSurface")
mesh.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
mesh.CreateDoubleSidedAttr().Set(True)

points_attr = mesh.CreatePointsAttr()
counts_attr = mesh.CreateFaceVertexCountsAttr()
indices_attr = mesh.CreateFaceVertexIndicesAttr()

records = []
t0 = time.perf_counter()

for frame, obj in enumerate(source_objects, start=1):
    src = obj.data

    points = Vt.Vec3fArray(
        [Gf.Vec3f(float(v.co.x), float(v.co.y), float(v.co.z)) for v in src.vertices]
    )

    counts = Vt.IntArray(len(src.polygons))
    flat_indices = []
    for i, poly in enumerate(src.polygons):
        verts = tuple(int(v) for v in poly.vertices)
        counts[i] = len(verts)
        flat_indices.extend(verts)
    indices = Vt.IntArray(flat_indices)

    time_code = Usd.TimeCode(frame)
    points_attr.Set(points, time_code)
    counts_attr.Set(counts, time_code)
    indices_attr.Set(indices, time_code)

    records.append(
        {
            "frame": frame,
            "vertices": len(src.vertices),
            "faces": len(src.polygons),
            "face_vertex_indices": len(flat_indices),
        }
    )

stage.GetRootLayer().Save()
seconds = time.perf_counter() - t0

if not USD_PATH.is_file() or USD_PATH.stat().st_size == 0:
    raise RuntimeError("direct USD file missing/empty")

# Verify authored time samples before handing the file to Blender's importer.
opened = Usd.Stage.Open(str(USD_PATH))
usd_mesh = UsdGeom.Mesh(opened.GetPrimAtPath("/FluidSurface"))

points_samples = usd_mesh.GetPointsAttr().GetTimeSamples()
counts_samples = usd_mesh.GetFaceVertexCountsAttr().GetTimeSamples()
indices_samples = usd_mesh.GetFaceVertexIndicesAttr().GetTimeSamples()

payload = {
    "path": USD_PATH.name,
    "bytes": USD_PATH.stat().st_size,
    "export_seconds": seconds,
    "prim_path": "/FluidSurface",
    "points_time_samples": points_samples,
    "face_counts_time_samples": counts_samples,
    "face_indices_time_samples": indices_samples,
    "frames": records,
}
METRICS_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2))

expected_samples = [float(i) for i in range(1, 14)]
if points_samples != expected_samples:
    raise RuntimeError(f"points samples mismatch: {points_samples}")
if counts_samples != expected_samples:
    raise RuntimeError(f"face counts samples mismatch: {counts_samples}")
if indices_samples != expected_samples:
    raise RuntimeError(f"face indices samples mismatch: {indices_samples}")
