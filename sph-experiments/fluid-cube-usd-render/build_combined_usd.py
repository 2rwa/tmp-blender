from __future__ import annotations

import json
import math
import shutil
import time
from pathlib import Path

from pxr import Gf, Usd, UsdGeom, Vt


ROOT = Path.cwd()
FLUID_USD = ROOT / "results" / "sph-direct-usd-topology" / "fluid-direct-single.usdc"
RIGID_JSON = ROOT / "sph-experiments" / "fluid-cube-usd-render" / "rigid_body_sequence.json"
OUT = ROOT / "output" / "sph-fluid-cube-render"
OUT.mkdir(parents=True, exist_ok=True)
COMBINED_USD = OUT / "fluid-cube.usdc"
METRICS = OUT / "combined-usd.json"


def to_blender(point):
    x, y, z = point
    return (float(x), float(-z), float(y))


def centroid(points):
    n = len(points)
    return tuple(sum(p[i] for p in points) / n for i in range(3))


if not FLUID_USD.is_file():
    raise RuntimeError(f"missing fluid USD: {FLUID_USD}")

rigid = json.loads(RIGID_JSON.read_text(encoding="utf-8"))
frames = rigid["frames"]
faces = rigid["faces"]
if len(frames) != 13:
    raise RuntimeError(f"expected 13 rigid frames, got {len(frames)}")
if len(faces) != 12:
    raise RuntimeError(f"expected 12 cube triangles, got {len(faces)}")

shutil.copy2(FLUID_USD, COMBINED_USD)
stage = Usd.Stage.Open(str(COMBINED_USD))
if not stage:
    raise RuntimeError("could not open copied fluid USD")

cube = UsdGeom.Mesh.Define(stage, "/DynamicCube")
cube.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
cube.CreateDoubleSidedAttr().Set(True)

points_attr = cube.CreatePointsAttr()
counts_attr = cube.CreateFaceVertexCountsAttr()
indices_attr = cube.CreateFaceVertexIndicesAttr()

counts = Vt.IntArray([len(face) for face in faces])
indices = Vt.IntArray([int(index) for face in faces for index in face])
counts_attr.Set(counts)
indices_attr.Set(indices)

records = []
t0 = time.perf_counter()
for record in frames:
    frame = int(record["frame"])
    converted = [to_blender(point) for point in record["points"]]
    if len(converted) != 8:
        raise RuntimeError(f"frame {frame}: expected 8 cube points, got {len(converted)}")
    points_attr.Set(
        Vt.Vec3fArray([Gf.Vec3f(*point) for point in converted]),
        Usd.TimeCode(frame),
    )
    center = centroid(converted)
    records.append(
        {
            "frame": frame,
            "centroid": [round(v, 9) for v in center],
            "vertices": len(converted),
            "faces": len(faces),
        }
    )

stage.SetStartTimeCode(1)
stage.SetEndTimeCode(13)
stage.SetFramesPerSecond(12)
stage.SetTimeCodesPerSecond(12)
stage.GetRootLayer().Save()
seconds = time.perf_counter() - t0

opened = Usd.Stage.Open(str(COMBINED_USD))
fluid = UsdGeom.Mesh(opened.GetPrimAtPath("/FluidSurface"))
cube_check = UsdGeom.Mesh(opened.GetPrimAtPath("/DynamicCube"))

fluid_samples = fluid.GetPointsAttr().GetTimeSamples()
cube_samples = cube_check.GetPointsAttr().GetTimeSamples()
expected = [float(i) for i in range(1, 14)]
if fluid_samples != expected:
    raise RuntimeError(f"fluid samples mismatch: {fluid_samples}")
if cube_samples != expected:
    raise RuntimeError(f"cube samples mismatch: {cube_samples}")

first = records[0]["centroid"]
last = records[-1]["centroid"]
displacement = math.dist(first, last)

payload = {
    "combined_usd": COMBINED_USD.name,
    "bytes": COMBINED_USD.stat().st_size,
    "author_seconds": seconds,
    "fluid_time_samples": fluid_samples,
    "cube_time_samples": cube_samples,
    "cube_frames": records,
    "cube_first_centroid_blender": first,
    "cube_last_centroid_blender": last,
    "cube_displacement_m": displacement,
}
METRICS.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2))
