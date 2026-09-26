from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path.cwd()
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RENDER_PATH = OUTPUT_DIR / "render.png"
BLEND_PATH = OUTPUT_DIR / "scene.blend"


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.cameras, bpy.data.lights):
        # Orphaned data is harmless, but clearing keeps repeated local runs deterministic.
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def make_material(name: str, base_color, metallic: float, roughness: float):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def smooth(obj) -> None:
    if getattr(obj.data, "polygons", None):
        for polygon in obj.data.polygons:
            polygon.use_smooth = True


def look_at(obj, point=(0.0, 0.0, 0.0)) -> None:
    direction = Vector(point) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_area_light(name: str, location, energy: float, size: float, color) -> None:
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, (0.0, 0.0, 0.4))


def choose_engine(scene) -> str:
    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = candidate
            return candidate
        except TypeError:
            continue
    scene.render.engine = "BLENDER_WORKBENCH"
    return "BLENDER_WORKBENCH"


def build_scene() -> None:
    clear_scene()
    scene = bpy.context.scene
    engine = choose_engine(scene)

    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.filepath = str(RENDER_PATH)

    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.008, 0.012, 0.025, 1.0)
    background.inputs["Strength"].default_value = 0.22

    floor_mat = make_material("Floor", (0.025, 0.035, 0.055), 0.15, 0.32)
    center_mat = make_material("Center", (0.06, 0.32, 0.72), 0.72, 0.17)
    warm_mat = make_material("WarmRing", (0.92, 0.19, 0.055), 0.42, 0.23)
    cool_mat = make_material("CoolRing", (0.02, 0.62, 0.78), 0.58, 0.19)
    torus_mat = make_material("Torus", (0.7, 0.72, 0.78), 0.84, 0.15)

    bpy.ops.mesh.primitive_plane_add(size=20.0, location=(0.0, 0.0, -1.55))
    floor = bpy.context.object
    floor.name = "Floor"
    floor.data.materials.append(floor_mat)

    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5, radius=1.35, location=(0.0, 0.0, 0.2))
    center = bpy.context.object
    center.name = "Core"
    center.data.materials.append(center_mat)
    smooth(center)

    bpy.ops.mesh.primitive_torus_add(
        major_radius=2.35,
        minor_radius=0.105,
        major_segments=96,
        minor_segments=18,
        location=(0.0, 0.0, 0.15),
        rotation=(math.radians(64.0), math.radians(14.0), math.radians(18.0)),
    )
    torus = bpy.context.object
    torus.name = "TiltedTorus"
    torus.data.materials.append(torus_mat)
    smooth(torus)

    for ring_index, (radius, z_base, material, phase) in enumerate(
        (
            (3.15, 0.28, warm_mat, 0.0),
            (3.75, 0.62, cool_mat, math.pi / 18.0),
        )
    ):
        count = 18
        for i in range(count):
            angle = 2.0 * math.pi * i / count + phase
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            z = z_base + 0.72 * math.sin(angle * 2.0 + ring_index * 0.9)
            orb_radius = 0.20 + 0.055 * (1.0 + math.sin(angle * 3.0))
            bpy.ops.mesh.primitive_uv_sphere_add(
                segments=24,
                ring_count=12,
                radius=orb_radius,
                location=(x, y, z),
            )
            orb = bpy.context.object
            orb.name = f"Ring{ring_index + 1}_{i:02d}"
            orb.data.materials.append(material)
            smooth(orb)

    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    camera.location = (8.7, -10.6, 7.4)
    camera_data.lens = 52.0
    camera_data.sensor_width = 36.0
    look_at(camera, (0.0, 0.0, 0.25))

    add_area_light("Key", (4.7, -4.0, 8.6), 1150.0, 5.0, (1.0, 0.76, 0.58))
    add_area_light("Fill", (-5.0, -1.8, 5.2), 850.0, 4.0, (0.35, 0.60, 1.0))
    add_area_light("Rim", (0.5, 6.6, 7.0), 1050.0, 3.5, (0.35, 0.82, 1.0))

    # A tiny bevel gives the floor a real geometry path while staying cheap.
    bevel = floor.modifiers.new(name="FloorBevel", type="BEVEL")
    bevel.width = 0.02
    bevel.segments = 2

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    bpy.ops.render.render(write_still=True)

    print(f"BLENDER_ENGINE={engine}")
    print(f"BLEND_PATH={BLEND_PATH}")
    print(f"RENDER_PATH={RENDER_PATH}")


if __name__ == "__main__":
    build_scene()
