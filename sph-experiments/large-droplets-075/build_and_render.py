from __future__ import annotations

import json
import math
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from pxr import Gf, Usd, UsdGeom, Vt


ROOT = Path.cwd()
BASE = ROOT / "output" / "sph-large-droplets-075"
CACHE = BASE / "cache"
MANIFEST_PATH = CACHE / "manifest.json"
USD_PATH = BASE / "fluid-cube-large-droplets-075.usdc"
BLEND_PATH = BASE / "fluid-cube-large-droplets-075.blend"
PREVIEW_PATH = BASE / "preview.png"
VIDEO_PATH = BASE / "media.mp4"
VALIDATION_PATH = BASE / "validation.json"


def to_blender_array(points: np.ndarray) -> np.ndarray:
    out = np.empty_like(points, dtype=np.float32)
    out[:, 0] = points[:, 0]
    out[:, 1] = -points[:, 2]
    out[:, 2] = points[:, 1]
    return out


def look_at(obj, point):
    direction = Vector(point) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def make_material(name, color, metallic=0.0, roughness=0.25):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def centroid_from_mesh(mesh):
    if not mesh.vertices:
        return (0.0, 0.0, 0.0)
    n = len(mesh.vertices)
    return tuple(sum(v.co[i] for v in mesh.vertices) / n for i in range(3))


def add_tank_wireframe():
    verts = [
        (-2, -1, 0), (2, -1, 0), (-2, 1, 0), (2, 1, 0),
        (-2, -1, 2), (2, -1, 2), (-2, 1, 2), (2, 1, 2),
    ]
    edges = [
        (0,1),(0,2),(1,3),(2,3),
        (4,5),(4,6),(5,7),(6,7),
        (0,4),(1,5),(2,6),(3,7),
    ]
    curve = bpy.data.curves.new("TankWireCurve", type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 1
    curve.bevel_depth = 0.012
    curve.bevel_resolution = 0
    for a, b in edges:
        spline = curve.splines.new("POLY")
        spline.points.add(1)
        spline.points[0].co = (*verts[a], 1.0)
        spline.points[1].co = (*verts[b], 1.0)
    obj = bpy.data.objects.new("TankWire", curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(
        make_material("TankWireMat", (0.18, 0.24, 0.30), metallic=0.2, roughness=0.35)
    )


manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
surface_records = manifest["surface_frames"]
rigid = manifest["rigid_body"]
frame_count = int(manifest["frames"])
if frame_count < 55:
    raise RuntimeError(f"expected long sequence, got {frame_count} frames")

# Author one topology-varying fluid mesh plus one animated cube.
t0 = time.perf_counter()
stage = Usd.Stage.CreateNew(str(USD_PATH))
stage.SetStartTimeCode(1)
stage.SetEndTimeCode(frame_count)
stage.SetFramesPerSecond(12)
stage.SetTimeCodesPerSecond(12)
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

fluid = UsdGeom.Mesh.Define(stage, "/FluidSurface")
fluid.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
fluid.CreateDoubleSidedAttr().Set(True)
fluid_points = fluid.CreatePointsAttr()
fluid_counts = fluid.CreateFaceVertexCountsAttr()
fluid_indices = fluid.CreateFaceVertexIndicesAttr()

for record in surface_records:
    frame = int(record["sequence_frame"])
    data = np.load(CACHE / "surfaces" / record["npz"])
    vertices = to_blender_array(np.asarray(data["vertices"], dtype=np.float32))
    triangles = np.asarray(data["triangles"], dtype=np.int32)
    if len(vertices) != int(record["vertices"]) or len(triangles) != int(record["faces"]):
        raise RuntimeError(f"frame {frame}: NPZ topology mismatch")

    fluid_points.Set(
        Vt.Vec3fArray([Gf.Vec3f(float(x), float(y), float(z)) for x, y, z in vertices]),
        Usd.TimeCode(frame),
    )
    fluid_counts.Set(Vt.IntArray([3] * len(triangles)), Usd.TimeCode(frame))
    fluid_indices.Set(Vt.IntArray(triangles.reshape(-1).tolist()), Usd.TimeCode(frame))

cube = UsdGeom.Mesh.Define(stage, "/DynamicCube")
cube.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
cube.CreateDoubleSidedAttr().Set(True)
cube_points = cube.CreatePointsAttr()
faces = rigid["faces"]
cube.CreateFaceVertexCountsAttr().Set(Vt.IntArray([len(face) for face in faces]))
cube.CreateFaceVertexIndicesAttr().Set(
    Vt.IntArray([int(i) for face in faces for i in face])
)
for record in rigid["frames"]:
    frame = int(record["sequence_frame"])
    points = to_blender_array(np.asarray(record["points"], dtype=np.float32))
    cube_points.Set(
        Vt.Vec3fArray([Gf.Vec3f(float(x), float(y), float(z)) for x, y, z in points]),
        Usd.TimeCode(frame),
    )

stage.GetRootLayer().Save()
usd_author_seconds = time.perf_counter() - t0
if not USD_PATH.is_file() or USD_PATH.stat().st_size == 0:
    raise RuntimeError("USD authoring failed")

# Fresh scene and import the cache just as a downstream Blender user would.
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

t0 = time.perf_counter()
result = bpy.ops.wm.usd_import(
    filepath=str(USD_PATH),
    set_frame_range=False,
    import_cameras=False,
    import_curves=False,
    import_lights=False,
    import_materials=False,
    import_meshes=True,
    import_volumes=False,
)
usd_import_seconds = time.perf_counter() - t0
if "FINISHED" not in result:
    raise RuntimeError(f"USD import failed: {result}")

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = frame_count
scene.render.fps = 12
scene.render.fps_base = 1.0

mesh_objects = {obj.name: obj for obj in scene.objects if obj.type == "MESH"}
fluid_obj = mesh_objects.get("FluidSurface")
cube_obj = mesh_objects.get("DynamicCube")
if fluid_obj is None or cube_obj is None or len(mesh_objects) != 2:
    raise RuntimeError(f"unexpected imported meshes: {sorted(mesh_objects)}")

water = make_material("Water", (0.025, 0.24, 0.72), metallic=0.08, roughness=0.12)
cube_mat = make_material("Cube", (0.95, 0.28, 0.045), metallic=0.15, roughness=0.22)
floor_mat = make_material("Floor", (0.035, 0.045, 0.06), roughness=0.5)
fluid_obj.data.materials.append(water)
cube_obj.data.materials.append(cube_mat)

bpy.ops.mesh.primitive_plane_add(size=8.0, location=(0, 0, 0))
floor = bpy.context.object
floor.name = "Floor"
floor.data.materials.append(floor_mat)
add_tank_wireframe()

scene.world.use_nodes = True
bg = scene.world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.008, 0.014, 0.028, 1.0)
bg.inputs["Strength"].default_value = 0.30

for name, location, energy, size, color in (
    ("Key", (3.8, -4.0, 5.5), 1100.0, 4.0, (1.0, 0.78, 0.60)),
    ("Fill", (-3.4, -1.5, 4.0), 700.0, 3.5, (0.42, 0.64, 1.0)),
    ("Rim", (0.0, 4.4, 5.0), 900.0, 3.0, (0.40, 0.78, 1.0)),
):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, (0.0, 0.0, 0.7))

camera_data = bpy.data.cameras.new("Camera")
camera = bpy.data.objects.new("Camera", camera_data)
bpy.context.collection.objects.link(camera)
scene.camera = camera
camera.location = (4.8, -7.2, 3.6)
camera_data.lens = 52.0
look_at(camera, (0.0, 0.0, 0.75))

for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
    try:
        scene.render.engine = engine
        break
    except TypeError:
        continue
scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.render.resolution_percentage = 100
scene.render.film_transparent = False

# Validate every frame before rendering.
depsgraph = bpy.context.evaluated_depsgraph_get()
observed = []
errors = []
centroids = []
t0 = time.perf_counter()
for i, record in enumerate(surface_records, start=1):
    scene.frame_set(i)
    bpy.context.view_layer.update()
    depsgraph.update()

    fe = fluid_obj.evaluated_get(depsgraph)
    fm = fe.to_mesh()
    try:
        got_fluid = (len(fm.vertices), len(fm.polygons))
    finally:
        fe.to_mesh_clear()
    expected_fluid = (int(record["vertices"]), int(record["faces"]))
    if got_fluid != expected_fluid:
        errors.append(f"frame {i}: fluid {got_fluid} != {expected_fluid}")

    ce = cube_obj.evaluated_get(depsgraph)
    cm = ce.to_mesh()
    try:
        got_cube = (len(cm.vertices), len(cm.polygons))
        center = centroid_from_mesh(cm)
    finally:
        ce.to_mesh_clear()
    if got_cube != (8, 12):
        errors.append(f"frame {i}: cube topology {got_cube}")
    centroids.append(center)
    observed.append(
        {
            "frame": i,
            "fluid_vertices": got_fluid[0],
            "fluid_faces": got_fluid[1],
            "cube_centroid": [round(v, 6) for v in center],
        }
    )
scrub_seconds = time.perf_counter() - t0

for name, obj in (("fluid", fluid_obj), ("cube", cube_obj)):
    modifiers = [m.type for m in obj.modifiers]
    if "MESH_SEQUENCE_CACHE" not in modifiers:
        errors.append(f"{name}: missing MESH_SEQUENCE_CACHE: {modifiers}")

if errors:
    raise RuntimeError("; ".join(errors))

centroids_np = np.asarray(centroids, dtype=np.float64)
steps = np.linalg.norm(np.diff(centroids_np, axis=0), axis=1)
dx = np.diff(centroids_np[:, 0])
reversals = int(
    np.sum(
        (np.sign(dx[:-1]) != 0)
        & (np.sign(dx[1:]) != 0)
        & (np.sign(dx[:-1]) != np.sign(dx[1:]))
    )
)

preview_frame = max(1, (frame_count + 1) // 2)
scene.frame_set(preview_frame)
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = str(PREVIEW_PATH)
bpy.ops.render.render(write_still=True)

scene.frame_set(1)
scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format = "MPEG4"
scene.render.ffmpeg.codec = "H264"
scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
scene.render.filepath = str(VIDEO_PATH)
render_t0 = time.perf_counter()
bpy.ops.render.render(animation=True)
render_seconds = time.perf_counter() - render_t0

scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
for cache in bpy.data.cache_files:
    cache.filepath = "//fluid-cube-large-droplets-075.usdc"
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

validation = {
    "variant": "large-droplets-075",
    "particle_radius": float(manifest["particle_radius"]),
    "smoothing_length": float(manifest["smoothing_length"]),
    "cube_size": float(manifest["cube_size"]),
    "radius_scale_vs_baseline": float(manifest.get("radius_scale_vs_baseline", 1.5)),
    "frames": frame_count,
    "duration_seconds": frame_count / 12.0,
    "fluid_mesh_objects": 1,
    "dynamic_cube_mesh_objects": 1,
    "fluid_modifier": [m.type for m in fluid_obj.modifiers],
    "cube_modifier": [m.type for m in cube_obj.modifiers],
    "surface_vertices_min": min(int(r["vertices"]) for r in surface_records),
    "surface_vertices_max": max(int(r["vertices"]) for r in surface_records),
    "surface_faces_min": min(int(r["faces"]) for r in surface_records),
    "surface_faces_max": max(int(r["faces"]) for r in surface_records),
    "surface_npz_total_bytes": int(manifest["surface_npz_total_bytes"]),
    "reconstruction_total_seconds": float(manifest["reconstruction_total_seconds"]),
    "usd_author_seconds": usd_author_seconds,
    "usd_import_seconds": usd_import_seconds,
    "scrub_all_frames_seconds": scrub_seconds,
    "render_seconds": render_seconds,
    "cube_path_length_m": float(np.sum(steps)),
    "cube_centroid_min_blender": [float(v) for v in np.min(centroids_np, axis=0)],
    "cube_centroid_max_blender": [float(v) for v in np.max(centroids_np, axis=0)],
    "cube_x_direction_reversals": reversals,
    "usd_bytes": USD_PATH.stat().st_size,
    "blend_bytes": BLEND_PATH.stat().st_size,
    "preview_bytes": PREVIEW_PATH.stat().st_size,
    "video_bytes": VIDEO_PATH.stat().st_size,
    "errors": errors,
    "observed": observed,
}
VALIDATION_PATH.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
print(json.dumps(validation, indent=2))
