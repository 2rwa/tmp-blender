from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path.cwd()
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VIDEO_PATH = OUTPUT_DIR / "fire-column.mp4"
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


def look_at(obj, point=(0.0, 0.0, 1.5)) -> None:
    direction = Vector(point) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def choose_engine(scene) -> str:
    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = candidate
            return candidate
        except TypeError:
            continue
    scene.render.engine = "BLENDER_WORKBENCH"
    return "BLENDER_WORKBENCH"


def make_emission(name: str, color, strength: float):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (*color, 1.0)
    emission.inputs["Strength"].default_value = strength
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return mat


def make_principled(name: str, color, metallic: float, roughness: float):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def setup_compositor(scene) -> None:
    scene.use_nodes = True
    nodes = scene.node_tree.nodes
    links = scene.node_tree.links
    nodes.clear()

    render_layers = nodes.new("CompositorNodeRLayers")
    glare = nodes.new("CompositorNodeGlare")
    glare.glare_type = "FOG_GLOW"
    glare.quality = "HIGH"
    glare.threshold = 0.5
    glare.size = 7
    composite = nodes.new("CompositorNodeComposite")

    links.new(render_layers.outputs["Image"], glare.inputs["Image"])
    links.new(glare.outputs["Image"], composite.inputs["Image"])


def add_flame_tongue(name: str, material, base_xy, radius: float, height: float, phase: float) -> None:
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=32,
        ring_count=16,
        radius=1.0,
        location=(base_xy[0], base_xy[1], 0.65 + height * 0.45),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    smooth(obj)

    for frame in (1, 13, 25, 37, 49, 61, 72):
        t = (frame - 1) / 71.0
        flicker = 1.0 + 0.18 * math.sin(t * math.tau * 3.0 + phase)
        lean_x = 0.18 * math.sin(t * math.tau * 2.0 + phase)
        lean_y = 0.12 * math.cos(t * math.tau * 2.6 + phase * 0.7)

        obj.location = (
            base_xy[0] + lean_x,
            base_xy[1] + lean_y,
            0.55 + height * 0.48 * flicker,
        )
        obj.scale = (
            radius * (0.95 + 0.08 * math.sin(phase + frame * 0.17)),
            radius * (0.90 + 0.09 * math.cos(phase + frame * 0.13)),
            height * flicker,
        )
        obj.rotation_euler = (
            0.10 * math.sin(frame * 0.09 + phase),
            0.12 * math.cos(frame * 0.07 + phase),
            0.06 * math.sin(frame * 0.11 + phase),
        )
        obj.keyframe_insert(data_path="location", frame=frame)
        obj.keyframe_insert(data_path="scale", frame=frame)
        obj.keyframe_insert(data_path="rotation_euler", frame=frame)


def add_sparks(material) -> None:
    for i in range(26):
        angle = (i * 2.399963229728653) % math.tau
        start = 1 + (i * 7) % 48
        peak = min(72, start + 11)
        end = min(72, start + 24)

        bpy.ops.mesh.primitive_ico_sphere_add(
            subdivisions=2,
            radius=0.045 + 0.015 * (i % 3),
            location=(0.0, 0.0, 0.65),
        )
        spark = bpy.context.object
        spark.name = f"Spark_{i:02d}"
        spark.data.materials.append(material)

        spark.scale = (0.0, 0.0, 0.0)
        spark.keyframe_insert(data_path="scale", frame=max(1, start - 1))

        spark.scale = (1.0, 1.0, 1.0)
        spark.keyframe_insert(data_path="scale", frame=start)

        radius = 0.35 + 0.55 * ((i % 5) / 4.0)
        spark.location = (
            math.cos(angle) * radius,
            math.sin(angle) * radius,
            1.6 + 0.08 * (i % 4),
        )
        spark.keyframe_insert(data_path="location", frame=peak)

        spark.location = (
            math.cos(angle) * radius * 1.45,
            math.sin(angle) * radius * 1.45,
            3.3 + 0.13 * (i % 6),
        )
        spark.keyframe_insert(data_path="location", frame=end)

        spark.scale = (0.0, 0.0, 0.0)
        spark.keyframe_insert(data_path="scale", frame=end)


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
    background.inputs["Color"].default_value = (0.003, 0.004, 0.008, 1.0)
    background.inputs["Strength"].default_value = 0.12

    setup_compositor(scene)

    flame_red = make_emission("FlameRed", (1.0, 0.05, 0.005), 3.5)
    flame_orange = make_emission("FlameOrange", (1.0, 0.24, 0.015), 7.0)
    flame_yellow = make_emission("FlameYellow", (1.0, 0.72, 0.10), 12.0)
    spark_mat = make_emission("Spark", (1.0, 0.56, 0.04), 16.0)
    metal = make_principled("BurnerMetal", (0.08, 0.09, 0.11), 0.85, 0.22)
    floor_mat = make_principled("Floor", (0.018, 0.020, 0.028), 0.35, 0.24)

    bpy.ops.mesh.primitive_plane_add(size=18.0, location=(0.0, 0.0, -0.18))
    floor = bpy.context.object
    floor.name = "Floor"
    floor.data.materials.append(floor_mat)

    bpy.ops.mesh.primitive_cylinder_add(
        vertices=64,
        radius=0.95,
        depth=0.32,
        location=(0.0, 0.0, 0.0),
    )
    burner = bpy.context.object
    burner.name = "Burner"
    burner.data.materials.append(metal)
    smooth(burner)

    tongues = [
        ("OuterA", flame_red, (-0.24, 0.05), 0.48, 1.55, 0.1),
        ("OuterB", flame_red, (0.26, -0.02), 0.44, 1.80, 1.4),
        ("OuterC", flame_red, (0.02, 0.18), 0.42, 2.10, 2.5),
        ("MidA", flame_orange, (-0.16, -0.03), 0.32, 1.60, 0.8),
        ("MidB", flame_orange, (0.18, 0.08), 0.30, 1.85, 2.0),
        ("MidC", flame_orange, (0.00, -0.10), 0.28, 2.25, 3.1),
        ("CoreA", flame_yellow, (-0.08, 0.02), 0.20, 1.20, 1.1),
        ("CoreB", flame_yellow, (0.10, -0.01), 0.18, 1.45, 2.7),
    ]
    for args in tongues:
        add_flame_tongue(*args)

    add_sparks(spark_mat)

    warm = bpy.data.lights.new(name="FireLight", type="POINT")
    warm.color = (1.0, 0.20, 0.03)
    warm.energy = 1050.0
    warm.shadow_soft_size = 2.0
    warm_obj = bpy.data.objects.new("FireLight", warm)
    bpy.context.collection.objects.link(warm_obj)
    warm_obj.location = (0.0, 0.0, 1.25)

    for frame, energy in ((1, 950.0), (13, 1250.0), (25, 880.0), (37, 1380.0), (49, 1020.0), (61, 1320.0), (72, 1000.0)):
        warm.energy = energy
        warm.keyframe_insert(data_path="energy", frame=frame)

    rim = bpy.data.lights.new(name="CoolRim", type="AREA")
    rim.energy = 650.0
    rim.color = (0.15, 0.32, 0.85)
    rim.shape = "DISK"
    rim.size = 4.0
    rim_obj = bpy.data.objects.new("CoolRim", rim)
    bpy.context.collection.objects.link(rim_obj)
    rim_obj.location = (-3.5, 2.5, 4.5)
    look_at(rim_obj, (0.0, 0.0, 1.0))

    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    camera.location = (5.6, -8.6, 3.7)
    camera_data.lens = 52.0
    look_at(camera, (0.0, 0.0, 1.35))

    camera.keyframe_insert(data_path="location", frame=1)
    camera.location = (5.1, -8.0, 3.5)
    camera.keyframe_insert(data_path="location", frame=72)

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.filepath = str(VIDEO_PATH)
    bpy.ops.render.render(animation=True)

    scene.frame_set(37)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(POSTER_PATH)
    bpy.ops.render.render(write_still=True)

    print(f"BLENDER_ENGINE={engine}")
    print(f"VIDEO_PATH={VIDEO_PATH}")
    print(f"POSTER_PATH={POSTER_PATH}")
    print(f"BLEND_PATH={BLEND_PATH}")


if __name__ == "__main__":
    build_scene()
