from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path.cwd()
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_PATH = OUTPUT_DIR / "water-dump.mp4"
POSTER_PATH = OUTPUT_DIR / "poster.png"
BLEND_PATH = OUTPUT_DIR / "scene.blend"


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def smooth(obj) -> None:
    if getattr(obj.data, "polygons", None):
        for polygon in obj.data.polygons:
            polygon.use_smooth = True


def look_at(obj, point=(0.0, 0.0, 0.6)) -> None:
    direction = Vector(point) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def set_input(bsdf, name: str, value) -> None:
    socket = bsdf.inputs.get(name)
    if socket is not None:
        socket.default_value = value


def make_material(name: str, color, metallic=0.0, roughness=0.2, transmission=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    set_input(bsdf, "Base Color", (*color, 1.0))
    set_input(bsdf, "Metallic", metallic)
    set_input(bsdf, "Roughness", roughness)
    set_input(bsdf, "Transmission Weight", transmission)
    set_input(bsdf, "Transmission", transmission)
    set_input(bsdf, "IOR", 1.333)
    return mat


def add_area_light(name: str, location, energy: float, size: float, color) -> None:
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj)


def choose_engine(scene) -> str:
    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = candidate
            return candidate
        except TypeError:
            continue
    scene.render.engine = "BLENDER_WORKBENCH"
    return "BLENDER_WORKBENCH"


def add_water_stream(material) -> None:
    curve = bpy.data.curves.new("PourStreamCurve", type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 16
    curve.bevel_depth = 0.34
    curve.bevel_resolution = 5

    spline = curve.splines.new("BEZIER")
    spline.bezier_points.add(3)
    coords = [
        (-1.45, 0.0, 3.45),
        (-1.18, 0.0, 2.75),
        (-0.70, 0.0, 1.55),
        (-0.05, 0.0, 0.40),
    ]
    for point, co in zip(spline.bezier_points, coords):
        point.co = co
        point.handle_left_type = "AUTO"
        point.handle_right_type = "AUTO"

    obj = bpy.data.objects.new("PourStream", curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(material)

    for frame, scale in (
        (1, 0.82),
        (24, 1.08),
        (48, 0.92),
        (72, 1.02),
    ):
        obj.scale = (scale, scale, scale)
        obj.keyframe_insert(data_path="scale", frame=frame)


def add_falling_droplets(material) -> None:
    for i in range(10):
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=20,
            ring_count=10,
            radius=0.16 + 0.025 * (i % 3),
            location=(-1.25, 0.0, 3.2),
        )
        drop = bpy.context.object
        drop.name = f"FallingDrop_{i:02d}"
        drop.data.materials.append(material)
        smooth(drop)

        start = 1 + i * 6
        mid = start + 16
        end = start + 28

        drop.scale = (0.0, 0.0, 0.0)
        drop.keyframe_insert(data_path="scale", frame=max(1, start - 2))

        drop.scale = (0.75, 0.75, 1.8)
        drop.keyframe_insert(data_path="scale", frame=start)

        drop.location = (-1.1 + 0.06 * math.sin(i), 0.06 * math.cos(i), 1.6)
        drop.keyframe_insert(data_path="location", frame=mid)

        drop.location = (-0.15 + 0.08 * math.sin(i * 1.7), 0.09 * math.cos(i * 1.3), 0.28)
        drop.keyframe_insert(data_path="location", frame=end)

        drop.scale = (0.0, 0.0, 0.0)
        drop.keyframe_insert(data_path="scale", frame=min(72, end + 5))


def add_splash(material) -> None:
    for i in range(20):
        angle = math.tau * i / 20
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=20,
            ring_count=10,
            radius=0.12 + 0.035 * ((i * 7) % 4),
            location=(0.0, 0.0, 0.20),
        )
        drop = bpy.context.object
        drop.name = f"Splash_{i:02d}"
        drop.data.materials.append(material)
        smooth(drop)

        drop.scale = (0.0, 0.0, 0.0)
        drop.keyframe_insert(data_path="scale", frame=14)

        drop.scale = (0.7, 0.7, 1.5)
        drop.keyframe_insert(data_path="scale", frame=20)

        radius = 0.9 + 0.45 * ((i % 5) / 4.0)
        drop.location = (
            math.cos(angle) * radius,
            math.sin(angle) * radius,
            0.65 + 0.45 * abs(math.sin(angle * 1.5)),
        )
        drop.keyframe_insert(data_path="location", frame=34)

        drop.location = (
            math.cos(angle) * radius * 1.45,
            math.sin(angle) * radius * 1.45,
            0.16,
        )
        drop.keyframe_insert(data_path="location", frame=52)

        drop.scale = (0.0, 0.0, 0.0)
        drop.keyframe_insert(data_path="scale", frame=62)


def build_scene() -> None:
    clear_scene()
    scene = bpy.context.scene
    engine = choose_engine(scene)

    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.frame_start = 1
    scene.frame_end = 72
    scene.render.film_transparent = False

    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.004, 0.012, 0.035, 1.0)
    background.inputs["Strength"].default_value = 0.30

    water = make_material("Water", (0.02, 0.28, 0.58), roughness=0.08, transmission=0.72)
    metal = make_material("SpoutMetal", (0.16, 0.20, 0.26), metallic=0.82, roughness=0.19)
    floor_mat = make_material("Floor", (0.018, 0.028, 0.045), metallic=0.15, roughness=0.32)

    bpy.ops.mesh.primitive_plane_add(size=18.0, location=(0.0, 0.0, -0.35))
    floor = bpy.context.object
    floor.name = "Floor"
    floor.data.materials.append(floor_mat)

    bpy.ops.mesh.primitive_plane_add(size=10.0, location=(0.0, 0.0, 0.0))
    pool = bpy.context.object
    pool.name = "WaterSurface"
    pool.data.materials.append(water)
    ocean = pool.modifiers.new(name="Ocean", type="OCEAN")
    ocean.geometry_mode = "GENERATE"
    ocean.resolution = 8
    ocean.spatial_size = 8
    ocean.wave_scale = 0.22
    ocean.choppiness = 0.75
    ocean.wind_velocity = 4.5
    ocean.wave_scale_min = 0.18
    ocean.time = 0.0
    ocean.keyframe_insert(data_path="time", frame=1)
    ocean.time = 1.6
    ocean.keyframe_insert(data_path="time", frame=72)

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64,
        radius=0.78,
        depth=2.5,
        location=(-2.1, 0.0, 4.0),
        rotation=(0.0, math.radians(63.0), 0.0),
    )
    spout = bpy.context.object
    spout.name = "TiltedSpout"
    spout.data.materials.append(metal)
    smooth(spout)

    add_water_stream(water)
    add_falling_droplets(water)
    add_splash(water)

    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    camera.location = (6.8, -10.5, 5.8)
    camera_data.lens = 48.0
    look_at(camera, (-0.2, 0.0, 1.0))
    camera.keyframe_insert(data_path="location", frame=1)
    camera.location = (6.1, -9.5, 5.2)
    camera.keyframe_insert(data_path="location", frame=72)

    add_area_light("Key", (3.2, -4.0, 8.0), 1350.0, 5.0, (0.72, 0.86, 1.0))
    add_area_light("Fill", (-4.0, -1.0, 5.0), 900.0, 4.0, (0.16, 0.46, 1.0))
    add_area_light("Rim", (1.0, 5.0, 6.5), 1250.0, 4.0, (0.18, 0.82, 1.0))

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.filepath = str(VIDEO_PATH)
    bpy.ops.render.render(animation=True)

    scene.frame_set(34)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(POSTER_PATH)
    bpy.ops.render.render(write_still=True)

    print(f"BLENDER_ENGINE={engine}")
    print(f"VIDEO_PATH={VIDEO_PATH}")
    print(f"POSTER_PATH={POSTER_PATH}")
    print(f"BLEND_PATH={BLEND_PATH}")


if __name__ == "__main__":
    build_scene()
