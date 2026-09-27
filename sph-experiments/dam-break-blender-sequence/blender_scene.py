from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path.cwd()
BASE = ROOT / "output" / "sph-blender-sequence"
SEQUENCE_DIR = BASE / "sequence"
SURFACE_DIR = SEQUENCE_DIR / "surfaces"
MANIFEST_PATH = SEQUENCE_DIR / "surface-sequence.json"
BLEND_DIR = BASE / "blender"
BLEND_DIR.mkdir(parents=True, exist_ok=True)
BLEND_PATH = BLEND_DIR / "surface-sequence.blend"
PREVIEW_PATH = BLEND_DIR / "preview.png"
VIDEO_PATH = BLEND_DIR / "surface-sequence.mp4"


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def look_at(obj, point) -> None:
    direction = Vector(point) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def make_material(name: str, color, roughness: float):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = 0.05
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = 1.333
    return mat


def add_area_light(name: str, location, energy: float, size: float) -> None:
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, (-0.2, 0.0, 0.8))


def import_surface(path: Path, frame: int, material) -> bpy.types.Object:
    before = set(bpy.context.scene.objects)
    bpy.ops.wm.obj_import(
        filepath=str(path),
        forward_axis="NEGATIVE_Z",
        up_axis="Y",
        use_split_objects=False,
        use_split_groups=False,
        validate_meshes=False,
    )
    created = [obj for obj in bpy.context.scene.objects if obj not in before]
    meshes = [obj for obj in created if obj.type == "MESH"]
    if len(meshes) != 1:
        raise RuntimeError(
            f"expected exactly one mesh object from {path}, got "
            f"{[(obj.name, obj.type) for obj in created]}"
        )

    obj = meshes[0]
    obj.name = f"FluidFrame_{frame:04d}"
    obj.data.name = f"FluidMesh_{frame:04d}"
    obj["sequence_frame"] = frame
    obj["source_obj"] = path.name
    obj.data.materials.clear()
    obj.data.materials.append(material)

    # Persist the topology-changing sequence as ordinary Blender animation:
    # exactly one mesh object has unit scale on each frame, all others scale to zero.
    obj.scale = (0.0, 0.0, 0.0)
    if frame > 1:
        obj.keyframe_insert(data_path="scale", frame=frame - 1)
    obj.scale = (1.0, 1.0, 1.0)
    obj.keyframe_insert(data_path="scale", frame=frame)
    if frame < FRAME_END:
        obj.scale = (0.0, 0.0, 0.0)
        obj.keyframe_insert(data_path="scale", frame=frame + 1)

    if obj.animation_data and obj.animation_data.action:
        for curve in obj.animation_data.action.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = "CONSTANT"

    return obj


manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
frames = manifest["frames"]
FRAME_START = 1
FRAME_END = len(frames)
FPS = int(manifest["fps"])

clear_scene()
scene = bpy.context.scene
scene.frame_start = FRAME_START
scene.frame_end = FRAME_END
scene.render.fps = FPS
scene.render.fps_base = 1.0

for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
    try:
        scene.render.engine = engine
        break
    except TypeError:
        continue

scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False
scene.world.use_nodes = True
background = scene.world.node_tree.nodes.get("Background")
background.inputs["Color"].default_value = (0.012, 0.018, 0.028, 1.0)
background.inputs["Strength"].default_value = 0.35

water_mat = make_material("SPHWater", (0.035, 0.30, 0.72), 0.16)
floor_mat = make_material("Floor", (0.035, 0.045, 0.055), 0.38)

objects = []
for record in frames:
    frame = int(record["blender_frame"])
    path = SURFACE_DIR / record["surface_obj"]
    if not path.is_file():
        raise FileNotFoundError(path)
    obj = import_surface(path, frame, water_mat)
    objects.append(obj)
    print(
        f"BLENDER_IMPORTED frame={frame} object={obj.name} "
        f"verts={len(obj.data.vertices)} faces={len(obj.data.polygons)}"
    )

bpy.ops.mesh.primitive_plane_add(size=12.0, location=(0.0, 0.0, 0.0))
floor = bpy.context.object
floor.name = "Floor"
floor.data.materials.append(floor_mat)

camera_data = bpy.data.cameras.new("Camera")
camera = bpy.data.objects.new("Camera", camera_data)
bpy.context.collection.objects.link(camera)
scene.camera = camera
camera.location = (4.7, -6.8, 3.5)
camera_data.lens = 52.0
look_at(camera, (-0.25, 0.0, 0.85))

add_area_light("Key", (3.8, -3.2, 6.0), 900.0, 4.0)
add_area_light("Fill", (-3.5, -1.5, 3.8), 650.0, 3.5)
add_area_light("Rim", (0.0, 4.5, 5.0), 850.0, 3.0)

scene.frame_set(FRAME_START)
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

preview_frame = max(FRAME_START, (FRAME_START + FRAME_END) // 2)
scene.frame_set(preview_frame)
scene.render.image_settings.file_format = "PNG"
scene.render.filepath = str(PREVIEW_PATH)
bpy.ops.render.render(write_still=True)

scene.frame_set(FRAME_START)
scene.render.image_settings.file_format = "FFMPEG"
scene.render.ffmpeg.format = "MPEG4"
scene.render.ffmpeg.codec = "H264"
scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
scene.render.filepath = str(VIDEO_PATH)
bpy.ops.render.render(animation=True)

scene.frame_set(FRAME_START)
bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

print(f"BLENDER_SEQUENCE_FRAMES={FRAME_END}")
print(f"BLENDER_BLEND={BLEND_PATH}")
print(f"BLENDER_PREVIEW={PREVIEW_PATH}")
print(f"BLENDER_VIDEO={VIDEO_PATH}")
