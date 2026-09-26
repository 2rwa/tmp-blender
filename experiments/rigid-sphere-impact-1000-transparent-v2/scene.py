# SPDX-License-Identifier: MIT-0
from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path.cwd()
OUTPUT = ROOT / "output"
OUTPUT.mkdir(parents=True, exist_ok=True)

VIDEO = OUTPUT / "rigid-sphere-impact-1000-transparent-v2.mp4"
POSTER = OUTPUT / "poster.png"
SIM_BLEND = OUTPUT / "rigid-sim.blend"
RESULT_BLEND = OUTPUT / "rigid-result.blend"

FRAME_START = 1
FRAME_END = 96
POSTER_FRAME = 44


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for blocks in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.curves,
    ):
        for block in list(blocks):
            if block.users == 0:
                blocks.remove(block)


def look_at(obj, point) -> None:
    direction = Vector(point) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def choose_engine(scene) -> str:
    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = candidate
            return candidate
        except TypeError:
            pass
    scene.render.engine = "BLENDER_WORKBENCH"
    return "BLENDER_WORKBENCH"


def apply_scale(obj) -> None:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.select_set(False)


def principled_material(name, base, metallic=0.0, roughness=0.45, transmission=0.0, alpha=1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = roughness
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    elif "Transmission" in bsdf.inputs:
        bsdf.inputs["Transmission"].default_value = transmission
    if "Alpha" in bsdf.inputs:
        bsdf.inputs["Alpha"].default_value = alpha
    return mat


def transparent_wall_material():
    mat = principled_material(
        "TransparentWall",
        (0.36, 0.66, 0.95),
        roughness=0.08,
        transmission=0.92,
        alpha=0.16,
    )
    if hasattr(mat, "blend_method"):
        mat.blend_method = "BLEND"
    if hasattr(mat, "shadow_method"):
        mat.shadow_method = "NONE"
    if hasattr(mat, "use_screen_refraction"):
        mat.use_screen_refraction = True
    return mat


def add_passive_box(name, location, dimensions, material=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    apply_scale(obj)
    if material is not None:
        obj.data.materials.append(material)

    bpy.ops.rigidbody.object_add()
    rb = obj.rigid_body
    rb.type = "PASSIVE"
    rb.collision_shape = "BOX"
    rb.friction = 0.82
    rb.restitution = 0.05
    return obj


def add_active_cube(name, location, size, material):
    bpy.ops.mesh.primitive_cube_add(size=size, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)

    bpy.ops.rigidbody.object_add()
    rb = obj.rigid_body
    rb.type = "ACTIVE"
    rb.mass = 0.22
    rb.friction = 0.70
    rb.restitution = 0.05
    rb.linear_damping = 0.035
    rb.angular_damping = 0.07
    rb.collision_shape = "BOX"
    return obj


def add_active_sphere(name, location, radius, material):
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=radius,
        location=location,
        segments=64,
        ring_count=32,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(material)
    bpy.ops.object.shade_smooth()

    bpy.ops.rigidbody.object_add()
    rb = obj.rigid_body
    rb.type = "ACTIVE"
    rb.mass = 22.0
    rb.friction = 0.50
    rb.restitution = 0.10
    rb.linear_damping = 0.008
    rb.angular_damping = 0.025
    rb.collision_shape = "SPHERE"
    return obj


def add_area_light(name, location, energy, size, color, target=(0.0, 0.0, 1.8)):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.shape = "RECTANGLE"
    data.size = size
    data.size_y = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, target)


def build_scene() -> None:
    clear_scene()
    scene = bpy.context.scene
    engine = choose_engine(scene)

    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.resolution_x = 960
    scene.render.resolution_y = 540
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.gravity = (0.0, 0.0, -9.81)
    scene.render.film_transparent = False

    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.010, 0.014, 0.024, 1.0)
    bg.inputs["Strength"].default_value = 0.34

    floor_mat = principled_material("Floor", (0.14, 0.16, 0.19), roughness=0.58)
    wall_mat = transparent_wall_material()
    block_mat = principled_material("Block", (0.54, 0.74, 0.98), roughness=0.30)
    sphere_mat = principled_material(
        "ImpactSphere",
        (1.0, 0.46, 0.10),
        metallic=0.22,
        roughness=0.20,
    )

    add_passive_box("Floor", (0.0, 0.0, -0.15), (15.0, 9.0, 0.3), floor_mat)

    # Walls remain in the physics simulation, but are visually glass-like.
    add_passive_box("WallLeft", (-3.55, 0.10, 2.15), (0.16, 8.0, 4.3), wall_mat)
    add_passive_box("WallRight", (3.55, 0.10, 2.15), (0.16, 8.0, 4.3), wall_mat)
    add_passive_box("WallBack", (0.0, 2.55, 2.15), (7.1, 0.16, 4.3), wall_mat)
    # Camera/front side is open.

    cam_data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    cam.location = (10.9, -10.2, 7.5)
    cam_data.lens = 46
    look_at(cam, (0.0, 0.0, 2.15))
    cam.keyframe_insert(data_path="location", frame=FRAME_START)
    cam.location = (9.7, -8.9, 6.6)
    cam.keyframe_insert(data_path="location", frame=FRAME_END)

    add_area_light("Key", (4.8, -5.4, 10.0), 2900.0, 5.8, (1.0, 0.92, 0.82))
    add_area_light("Rim", (-5.8, 3.8, 7.8), 1850.0, 4.4, (0.34, 0.56, 1.0))
    add_area_light("Fill", (3.5, 3.4, 4.6), 1100.0, 4.2, (1.0, 0.57, 0.27))

    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    rbw = scene.rigidbody_world
    rbw.point_cache.frame_start = FRAME_START
    rbw.point_cache.frame_end = FRAME_END
    rbw.substeps_per_frame = 12
    rbw.solver_iterations = 30

    size = 0.22
    gap = 0.018
    start_x = -1.071
    start_y = -1.071
    start_z = 0.14

    count = 0
    for iz in range(10):
        for iy in range(10):
            for ix in range(10):
                x = start_x + ix * (size + gap)
                y = start_y + iy * (size + gap)
                z = start_z + iz * (size + gap)
                obj = add_active_cube(
                    f"Block_{count:04d}",
                    (x, y, z),
                    size,
                    block_mat,
                )
                obj.rotation_euler = (
                    math.radians((ix % 3) * 1.25),
                    math.radians((iy % 4) * 0.95),
                    math.radians((iz % 5) * 0.85),
                )
                count += 1

    impact_sphere = add_active_sphere(
        "ImpactSphere",
        (0.26, -0.08, 6.9),
        0.88,
        sphere_mat,
    )
    impact_sphere.rotation_euler = (
        math.radians(11.0),
        math.radians(-7.0),
        math.radians(4.0),
    )

    print("RIGID_BAKE_BEGIN")
    result = bpy.ops.ptcache.bake_all(bake=True)
    print(f"RIGID_BAKE_RESULT={sorted(result)}")

    bpy.ops.wm.save_as_mainfile(filepath=str(SIM_BLEND))

    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.filepath = str(VIDEO)
    bpy.ops.render.render(animation=True)

    scene.frame_set(POSTER_FRAME)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(POSTER)
    bpy.ops.render.render(write_still=True)

    bpy.ops.wm.save_as_mainfile(filepath=str(RESULT_BLEND), copy=True)

    print(f"RIGID_BODY_CUBE_COUNT={count}")
    print("IMPACT_SPHERE_COUNT=1")
    print("TRANSPARENT_WALLS=3")
    print(f"BLENDER_ENGINE={engine}")
    print(f"VIDEO_PATH={VIDEO}")
    print(f"SIM_BLEND_PATH={SIM_BLEND}")
    print(f"RESULT_BLEND_PATH={RESULT_BLEND}")


if __name__ == "__main__":
    build_scene()
