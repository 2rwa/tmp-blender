from __future__ import annotations

import json
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from pxr import Gf, Usd, UsdGeom, Vt


ROOT = Path.cwd()
BASE = ROOT / "output" / "sph-geometry-nodes-points-volume"
CACHE = BASE / "points"
MANIFEST = json.loads((CACHE / "manifest.json").read_text(encoding="utf-8"))
USD_PATH = BASE / "sph-points.usdc"
BLEND_PATH = BASE / "sph-points-geometry-nodes.blend"
PREVIEW_PATH = BASE / "preview.png"
VIDEO_PATH = BASE / "media.mp4"
VALIDATION_PATH = BASE / "validation.json"

RADIUS = 0.10
VOXEL_SIZE = 0.04
THRESHOLD = 0.10


def to_blender(points: np.ndarray) -> np.ndarray:
    out = np.empty_like(points, dtype=np.float32)
    out[:, 0] = points[:, 0]
    out[:, 1] = -points[:, 2]
    out[:, 2] = points[:, 1]
    return out


def look_at(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()


def material(name, base, metallic=0.0, roughness=0.2):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def find_socket(collection, name):
    sock = collection.get(name)
    if sock is None:
        raise RuntimeError(f"socket {name!r} not found; have {[s.name for s in collection]}")
    return sock


def make_geometry_nodes(obj, water_mat):
    group = bpy.data.node_groups.new("SPH Points To Water Surface", "GeometryNodeTree")
    group.is_modifier = True

    in_geo = group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    out_geo = group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    radius = group.interface.new_socket(name="Radius", in_out="INPUT", socket_type="NodeSocketFloat")
    radius.default_value = RADIUS
    radius.min_value = 0.01
    radius.max_value = 0.30
    voxel = group.interface.new_socket(name="Voxel Size", in_out="INPUT", socket_type="NodeSocketFloat")
    voxel.default_value = VOXEL_SIZE
    voxel.min_value = 0.01
    voxel.max_value = 0.15
    threshold = group.interface.new_socket(name="Threshold", in_out="INPUT", socket_type="NodeSocketFloat")
    threshold.default_value = THRESHOLD
    threshold.min_value = 0.001
    threshold.max_value = 1.0

    nodes = group.nodes
    links = group.links
    gin = nodes.new("NodeGroupInput")
    gin.location = (-650, 0)
    gout = nodes.new("NodeGroupOutput")
    gout.location = (500, 0)

    mesh_to_points = nodes.new("GeometryNodeMeshToPoints")
    mesh_to_points.location = (-430, 0)
    mesh_to_points.mode = "VERTICES"

    points_to_volume = nodes.new("GeometryNodePointsToVolume")
    points_to_volume.location = (-160, 0)
    points_to_volume.resolution_mode = "VOXEL_SIZE"
    find_socket(points_to_volume.inputs, "Density").default_value = 1.0

    volume_to_mesh = nodes.new("GeometryNodeVolumeToMesh")
    volume_to_mesh.location = (100, 0)
    volume_to_mesh.resolution_mode = "GRID"
    find_socket(volume_to_mesh.inputs, "Adaptivity").default_value = 0.0

    set_material = nodes.new("GeometryNodeSetMaterial")
    set_material.location = (310, 0)
    find_socket(set_material.inputs, "Material").default_value = water_mat

    links.new(find_socket(gin.outputs, "Geometry"), find_socket(mesh_to_points.inputs, "Mesh"))
    links.new(find_socket(mesh_to_points.outputs, "Points"), find_socket(points_to_volume.inputs, "Points"))
    links.new(find_socket(gin.outputs, "Radius"), find_socket(points_to_volume.inputs, "Radius"))
    links.new(find_socket(gin.outputs, "Voxel Size"), find_socket(points_to_volume.inputs, "Voxel Size"))
    links.new(find_socket(points_to_volume.outputs, "Volume"), find_socket(volume_to_mesh.inputs, "Volume"))
    links.new(find_socket(gin.outputs, "Threshold"), find_socket(volume_to_mesh.inputs, "Threshold"))
    links.new(find_socket(volume_to_mesh.outputs, "Mesh"), find_socket(set_material.inputs, "Geometry"))
    links.new(find_socket(set_material.outputs, "Geometry"), find_socket(gout.inputs, "Geometry"))

    modifier = obj.modifiers.new("SPH Points -> Volume -> Mesh", "NODES")
    modifier.node_group = group
    return modifier, group


# Direct USD: vertex-only mesh with time-sampled particle positions + animated rigid cube.
stage = Usd.Stage.CreateNew(str(USD_PATH))
stage.SetStartTimeCode(1)
stage.SetEndTimeCode(MANIFEST["frames"])
stage.SetFramesPerSecond(MANIFEST["fps"])
stage.SetTimeCodesPerSecond(MANIFEST["fps"])
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

particles = UsdGeom.Mesh.Define(stage, "/SPHPoints")
particles.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
particles.CreateFaceVertexCountsAttr().Set(Vt.IntArray([]))
particles.CreateFaceVertexIndicesAttr().Set(Vt.IntArray([]))
p_points = particles.CreatePointsAttr()

cube = UsdGeom.Mesh.Define(stage, "/DynamicCube")
cube.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
cube.CreateDoubleSidedAttr().Set(True)
cube.CreateFaceVertexCountsAttr().Set(Vt.IntArray([3] * len(MANIFEST["cube_faces"])))
cube.CreateFaceVertexIndicesAttr().Set(
    Vt.IntArray([int(i) for face in MANIFEST["cube_faces"] for i in face])
)
c_points = cube.CreatePointsAttr()

author_t0 = time.perf_counter()
for record in MANIFEST["frames_data"]:
    frame = int(record["sequence_frame"])
    data = np.load(CACHE / record["file"])
    pts = to_blender(np.asarray(data["points"], dtype=np.float32))
    cub = to_blender(np.asarray(data["cube"], dtype=np.float32))
    p_points.Set(
        Vt.Vec3fArray([Gf.Vec3f(float(x), float(y), float(z)) for x, y, z in pts]),
        Usd.TimeCode(frame),
    )
    c_points.Set(
        Vt.Vec3fArray([Gf.Vec3f(float(x), float(y), float(z)) for x, y, z in cub]),
        Usd.TimeCode(frame),
    )
stage.GetRootLayer().Save()
author_seconds = time.perf_counter() - author_t0

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

import_t0 = time.perf_counter()
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
import_seconds = time.perf_counter() - import_t0
if "FINISHED" not in result:
    raise RuntimeError(f"USD import failed: {result}")

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = MANIFEST["frames"]
scene.render.fps = MANIFEST["fps"]

point_obj = bpy.data.objects.get("SPHPoints")
cube_obj = bpy.data.objects.get("DynamicCube")
if point_obj is None or cube_obj is None:
    raise RuntimeError(f"missing imported objects: {[o.name for o in scene.objects]}")

water = material("Water", (0.02, 0.22, 0.68), metallic=0.05, roughness=0.10)
cube_mat = material("Cube", (0.95, 0.27, 0.04), metallic=0.12, roughness=0.24)
floor_mat = material("Floor", (0.035, 0.045, 0.06), roughness=0.5)
cube_obj.data.materials.append(cube_mat)

gn_modifier, node_group = make_geometry_nodes(point_obj, water)

# Ground and lighting.
bpy.ops.mesh.primitive_plane_add(size=8.0, location=(0, 0, 0))
floor = bpy.context.object
floor.name = "Floor"
floor.data.materials.append(floor_mat)

scene.world.use_nodes = True
bg = scene.world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.008, 0.014, 0.028, 1.0)
bg.inputs["Strength"].default_value = 0.30

for name, location, energy, size, color in (
    ("Key", (3.8, -4.0, 5.5), 1200.0, 4.0, (1.0, 0.78, 0.60)),
    ("Fill", (-3.4, -1.5, 4.0), 750.0, 3.5, (0.42, 0.64, 1.0)),
    ("Rim", (0.0, 4.4, 5.0), 900.0, 3.0, (0.40, 0.78, 1.0)),
):
    ld = bpy.data.lights.new(name=name, type="AREA")
    ld.energy = energy
    ld.shape = "DISK"
    ld.size = size
    ld.color = color
    lo = bpy.data.objects.new(name, ld)
    bpy.context.collection.objects.link(lo)
    lo.location = location
    look_at(lo, (0.0, 0.0, 0.7))

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
        pass
scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.render.resolution_percentage = 100

# Validate source points and evaluated GN surface on representative frames.
checks = []
errors = []
depsgraph = bpy.context.evaluated_depsgraph_get()
check_frames = [1, 7, 13, 31, 46, 61]
check_t0 = time.perf_counter()
for frame in check_frames:
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    depsgraph.update()

    raw_eval = point_obj.evaluated_get(depsgraph)
    mesh = raw_eval.to_mesh()
    try:
        out_vertices = len(mesh.vertices)
        out_faces = len(mesh.polygons)
    finally:
        raw_eval.to_mesh_clear()

    if out_vertices <= 0 or out_faces <= 0:
        errors.append(f"frame {frame}: empty GN surface {out_vertices}/{out_faces}")

    checks.append({
        "frame": frame,
        "source_particles": MANIFEST["particle_count"],
        "surface_vertices": out_vertices,
        "surface_faces": out_faces,
    })
check_seconds = time.perf_counter() - check_t0

mod_types = [m.type for m in point_obj.modifiers]
if "MESH_SEQUENCE_CACHE" not in mod_types or "NODES" not in mod_types:
    errors.append(f"unexpected point modifier stack: {mod_types}")
required_nodes = {
    "GeometryNodeMeshToPoints",
    "GeometryNodePointsToVolume",
    "GeometryNodeVolumeToMesh",
}
actual_nodes = {n.bl_idname for n in node_group.nodes}
missing = sorted(required_nodes - actual_nodes)
if missing:
    errors.append(f"missing GN nodes: {missing}")
if errors:
    raise RuntimeError("; ".join(errors))

preview_frame = 31
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
for cache_file in bpy.data.cache_files:
    cache_file.filepath = "//sph-points.usdc"
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

validation = {
    "representation": "animated-vertex-only-usd-plus-geometry-nodes",
    "frames": MANIFEST["frames"],
    "particle_count": MANIFEST["particle_count"],
    "point_attributes_cached": MANIFEST["attributes"],
    "point_npz_total_bytes": MANIFEST["point_npz_total_bytes"],
    "point_usd_bytes": USD_PATH.stat().st_size,
    "blend_bytes": BLEND_PATH.stat().st_size,
    "preview_bytes": PREVIEW_PATH.stat().st_size,
    "video_bytes": VIDEO_PATH.stat().st_size,
    "usd_author_seconds": author_seconds,
    "usd_import_seconds": import_seconds,
    "geometry_nodes_check_seconds": check_seconds,
    "render_seconds": render_seconds,
    "geometry_nodes": {
        "radius": RADIUS,
        "voxel_size": VOXEL_SIZE,
        "threshold": THRESHOLD,
        "nodes": sorted(actual_nodes),
        "modifier_stack": mod_types,
        "exposed_inputs": ["Radius", "Voxel Size", "Threshold"],
    },
    "checks": checks,
    "errors": errors,
}
VALIDATION_PATH.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
print(json.dumps(validation, indent=2))
