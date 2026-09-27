from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path.cwd()
OUT = ROOT / "output" / "sph-fluid-cube-render"
USD_PATH = OUT / "fluid-cube.usdc"
METRICS_PATH = OUT / "combined-usd.json"
BLEND_PATH = OUT / "fluid-cube.blend"
PREVIEW_PATH = OUT / "preview.png"
VIDEO_PATH = OUT / "media.mp4"
VALIDATION_PATH = OUT / "validation.json"

EXPECTED_FLUID = [
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


def look_at(obj, point):
    direction = Vector(point) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def material(name, color, metallic=0.0, roughness=0.25):
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


bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

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
if "FINISHED" not in result:
    raise RuntimeError(f"USD import failed: {result}")

scene = bpy.context.scene
scene.frame_start = 1
scene.frame_end = 13
scene.render.fps = 12
scene.render.fps_base = 1.0

meshes = {obj.name: obj for obj in scene.objects if obj.type == "MESH"}
fluid = meshes.get("FluidSurface")
cube = meshes.get("DynamicCube")
if fluid is None or cube is None:
    raise RuntimeError(f"expected FluidSurface and DynamicCube, got {sorted(meshes)}")
if len(meshes) != 2:
    raise RuntimeError(f"expected exactly 2 imported mesh objects, got {sorted(meshes)}")

water = material("Water", (0.025, 0.24, 0.72), metallic=0.08, roughness=0.12)
cube_mat = material("DynamicCubeMat", (0.95, 0.28, 0.045), metallic=0.15, roughness=0.22)
floor_mat = material("FloorMat", (0.035, 0.045, 0.06), metallic=0.0, roughness=0.5)
fluid.data.materials.clear()
fluid.data.materials.append(water)
cube.data.materials.clear()
cube.data.materials.append(cube_mat)

# Keep the cache portable beside the saved Blend.
for cache in bpy.data.cache_files:
    cache.filepath = "//fluid-cube.usdc"

bpy.ops.mesh.primitive_plane_add(size=8.0, location=(0.0, 0.0, 0.0))
floor = bpy.context.object
floor.name = "Floor"
floor.data.materials.append(floor_mat)

scene.world.use_nodes = True
background = scene.world.node_tree.nodes.get("Background")
background.inputs["Color"].default_value = (0.008, 0.014, 0.028, 1.0)
background.inputs["Strength"].default_value = 0.30

for name, location, energy, size, color in (
    ("Key", (3.6, -3.4, 5.0), 1000.0, 4.0, (1.0, 0.78, 0.60)),
    ("Fill", (-3.0, -1.0, 3.8), 700.0, 3.5, (0.42, 0.64, 1.0)),
    ("Rim", (1.0, 4.0, 4.5), 900.0, 3.0, (0.40, 0.78, 1.0)),
):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, (0.2, 0.0, 0.65))

camera_data = bpy.data.cameras.new("Camera")
camera = bpy.data.objects.new("Camera", camera_data)
bpy.context.collection.objects.link(camera)
scene.camera = camera
camera.location = (4.5, -6.4, 3.1)
camera_data.lens = 50.0
look_at(camera, (0.25, 0.0, 0.65))

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

depsgraph = bpy.context.evaluated_depsgraph_get()
observed = []
errors = []
for frame in range(1, 14):
    scene.frame_set(frame)
    bpy.context.view_layer.update()
    depsgraph.update()

    fluid_eval = fluid.evaluated_get(depsgraph)
    fm = fluid_eval.to_mesh()
    try:
        fluid_topology = (len(fm.vertices), len(fm.polygons))
    finally:
        fluid_eval.to_mesh_clear()

    cube_eval = cube.evaluated_get(depsgraph)
    cm = cube_eval.to_mesh()
    try:
        cube_topology = (len(cm.vertices), len(cm.polygons))
        center = centroid_from_mesh(cm)
    finally:
        cube_eval.to_mesh_clear()

    if fluid_topology != EXPECTED_FLUID[frame - 1]:
        errors.append(
            f"frame {frame}: fluid topology {fluid_topology} != {EXPECTED_FLUID[frame - 1]}"
        )
    if cube_topology != (8, 12):
        errors.append(f"frame {frame}: cube topology {cube_topology} != (8, 12)")

    observed.append(
        {
            "frame": frame,
            "fluid_vertices": fluid_topology[0],
            "fluid_faces": fluid_topology[1],
            "cube_vertices": cube_topology[0],
            "cube_faces": cube_topology[1],
            "cube_centroid": [round(v, 6) for v in center],
        }
    )

first = observed[0]["cube_centroid"]
last = observed[-1]["cube_centroid"]
displacement = math.dist(first, last)
if displacement < 1.9:
    errors.append(f"cube displacement unexpectedly small: {displacement}")

for name, obj in (("fluid", fluid), ("cube", cube)):
    mods = [m.type for m in obj.modifiers]
    if "MESH_SEQUENCE_CACHE" not in mods:
        errors.append(f"{name}: missing MESH_SEQUENCE_CACHE, got {mods}")

if errors:
    raise RuntimeError("; ".join(errors))

scene.frame_set(7)
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = str(PREVIEW_PATH)
bpy.ops.render.render(write_still=True)

scene.frame_set(1)
scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format = "MPEG4"
scene.render.ffmpeg.codec = "H264"
scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
scene.render.filepath = str(VIDEO_PATH)
bpy.ops.render.render(animation=True)

scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
validation = {
    "frames": 13,
    "fluid_mesh_objects": 1,
    "dynamic_cube_mesh_objects": 1,
    "imported_mesh_objects": 2,
    "fluid_modifier": [m.type for m in fluid.modifiers],
    "cube_modifier": [m.type for m in cube.modifiers],
    "cube_first_centroid_blender": first,
    "cube_last_centroid_blender": last,
    "cube_displacement_m": displacement,
    "combined_usd_bytes": USD_PATH.stat().st_size,
    "blend_bytes": BLEND_PATH.stat().st_size,
    "preview_bytes": PREVIEW_PATH.stat().st_size,
    "video_bytes": VIDEO_PATH.stat().st_size,
    "errors": errors,
    "observed": observed,
    "source_metrics": metrics,
}
VALIDATION_PATH.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
print(json.dumps(validation, indent=2))
