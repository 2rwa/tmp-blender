from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path.cwd()
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BLEND_PATH = OUTPUT_DIR / "cloth-hammock-collision-eevee.blend"
REPORT_PATH = OUTPUT_DIR / "cloth-hammock-collision-eevee-report.json"

FRAME_START = 1
FRAME_END = 96
FPS = 24
RES_X = 480
RES_Y = 360
PREPARE_ONLY = os.environ.get("BLENDER_PREPARE_ONLY") == "1"

GRID_X = 45
GRID_Y = 35
WIDTH = 5.6
DEPTH = 4.2
CLOTH_Z = 2.8


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


def choose_engine(scene) -> str:
    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = candidate
            return candidate
        except TypeError:
            continue
    scene.render.engine = "BLENDER_WORKBENCH"
    return "BLENDER_WORKBENCH"


def configure_render(scene) -> int | None:
    eevee = getattr(scene, "eevee", None)
    if eevee is not None and hasattr(eevee, "taa_render_samples"):
        eevee.taa_render_samples = 16
        if hasattr(eevee, "use_gtao"):
            eevee.use_gtao = True
        if hasattr(eevee, "gtao_distance"):
            eevee.gtao_distance = 3.0
        if hasattr(eevee, "gtao_factor"):
            eevee.gtao_factor = 1.25
        return int(eevee.taa_render_samples)
    return None


def look_at(obj, target) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def make_material(name: str, base_color, roughness=0.55, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def make_cloth_material():
    mat = bpy.data.materials.new("ClothFabric")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.72

    checker = nodes.new("ShaderNodeTexChecker")
    checker.inputs["Color1"].default_value = (0.04, 0.12, 0.55, 1.0)
    checker.inputs["Color2"].default_value = (0.85, 0.12, 0.035, 1.0)
    checker.inputs["Scale"].default_value = 10.0

    texcoord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (1.0, 0.8, 1.0)

    links.new(texcoord.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], checker.inputs["Vector"])
    links.new(checker.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def make_grid_mesh(name: str):
    verts = []
    faces = []
    for j in range(GRID_Y):
        y = -DEPTH * 0.5 + DEPTH * j / (GRID_Y - 1)
        for i in range(GRID_X):
            x = -WIDTH * 0.5 + WIDTH * i / (GRID_X - 1)
            z = CLOTH_Z + 0.025 * math.sin(i * 0.47) * math.sin(j * 0.39)
            verts.append((x, y, z))

    for j in range(GRID_Y - 1):
        for i in range(GRID_X - 1):
            a = j * GRID_X + i
            b = a + 1
            c = a + GRID_X + 1
            d = a + GRID_X
            faces.append((a, b, c, d))

    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def make_pin_group(cloth):
    group = cloth.vertex_groups.new(name="PinCorners")
    pinned = []
    patch = 2
    for j in range(GRID_Y):
        for i in range(GRID_X):
            near_x = i <= patch or i >= GRID_X - 1 - patch
            near_y = j <= patch or j >= GRID_Y - 1 - patch
            if near_x and near_y:
                pinned.append(j * GRID_X + i)
    group.add(pinned, 1.0, "REPLACE")
    return group, pinned


def add_cloth_modifier(cloth, pin_group):
    mod = cloth.modifiers.new(name="ClothPhysics", type="CLOTH")
    s = mod.settings
    s.quality = 8
    s.mass = 0.28
    s.air_damping = 1.4
    s.tension_stiffness = 34.0
    s.compression_stiffness = 34.0
    s.shear_stiffness = 24.0
    s.bending_stiffness = 0.65
    s.tension_damping = 7.0
    s.compression_damping = 7.0
    s.shear_damping = 7.0
    s.bending_damping = 2.5
    s.pin_stiffness = 22.0
    s.vertex_group_mass = pin_group.name
    s.time_scale = 1.0

    c = mod.collision_settings
    c.use_collision = True
    c.collision_quality = 4
    c.distance_min = 0.012
    c.friction = 6.0
    c.use_self_collision = True
    c.self_distance_min = 0.012
    c.self_friction = 3.0

    cache = mod.point_cache
    cache.frame_start = FRAME_START
    cache.frame_end = FRAME_END
    cache.frame_step = 1
    return mod


def add_collision(obj, friction=8.0, thickness=0.035):
    obj.modifiers.new(name="Collision", type="COLLISION")
    obj.collision.use = True
    obj.collision.cloth_friction = friction
    obj.collision.thickness_outer = thickness


def keyframe_location(obj, frame: int, xyz) -> None:
    obj.location = xyz
    obj.keyframe_insert(data_path="location", frame=frame)


def make_colliders():
    ball_mat = make_material("BallA", (0.055, 0.075, 0.11), roughness=0.25, metallic=0.65)
    ball2_mat = make_material("BallB", (0.12, 0.045, 0.025), roughness=0.32, metallic=0.48)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20, radius=0.72, location=(0.0, 0.0, 5.2))
    ball_a = bpy.context.object
    ball_a.name = "BallAbove"
    ball_a.data.materials.append(ball_mat)
    add_collision(ball_a, friction=10.0, thickness=0.04)
    keyframe_location(ball_a, 1, (-0.5, -0.25, 5.2))
    keyframe_location(ball_a, 18, (-0.5, -0.25, 4.7))
    keyframe_location(ball_a, 42, (-0.25, -0.10, 2.72))
    keyframe_location(ball_a, 68, (1.15, 0.75, 2.45))
    keyframe_location(ball_a, 82, (1.75, 1.05, 2.75))
    keyframe_location(ball_a, 96, (2.25, 1.35, 4.15))

    bpy.ops.mesh.primitive_uv_sphere_add(segments=28, ring_count=18, radius=0.52, location=(-1.5, -0.8, 0.7))
    ball_b = bpy.context.object
    ball_b.name = "BallBelow"
    ball_b.data.materials.append(ball2_mat)
    add_collision(ball_b, friction=7.0, thickness=0.035)
    keyframe_location(ball_b, 1, (-1.55, -0.95, 0.65))
    keyframe_location(ball_b, 46, (-1.55, -0.95, 0.8))
    keyframe_location(ball_b, 66, (-1.25, -0.65, 2.3))
    keyframe_location(ball_b, 82, (-0.65, 0.15, 2.5))
    keyframe_location(ball_b, 96, (-0.35, 0.45, 1.0))

    for obj in (ball_a, ball_b):
        if obj.animation_data and obj.animation_data.action:
            for fc in obj.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "BEZIER"

    return ball_a, ball_b


def make_supports_and_ground():
    dark = make_material("Supports", (0.025, 0.028, 0.034), roughness=0.4, metallic=0.72)
    ground_mat = make_material("Ground", (0.018, 0.02, 0.026), roughness=0.88, metallic=0.02)

    bpy.ops.mesh.primitive_plane_add(size=16.0, location=(0.0, 0.0, -0.02))
    ground = bpy.context.object
    ground.name = "Ground"
    ground.data.materials.append(ground_mat)

    for x in (-WIDTH * 0.5, WIDTH * 0.5):
        for y in (-DEPTH * 0.5, DEPTH * 0.5):
            bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.07, depth=2.9, location=(x, y, 1.4))
            post = bpy.context.object
            post.data.materials.append(dark)

            bpy.ops.mesh.primitive_uv_sphere_add(segments=18, ring_count=10, radius=0.11, location=(x, y, CLOTH_Z))
            cap = bpy.context.object
            cap.data.materials.append(dark)


def make_effectors():
    bpy.ops.object.effector_add(type="WIND", location=(-4.5, -0.2, 3.0))
    wind = bpy.context.object
    wind.name = "CrossWind"
    wind.rotation_euler = (0.0, math.radians(90.0), math.radians(6.0))
    wind.field.strength = 520.0
    wind.field.noise = 1.4

    bpy.ops.object.effector_add(type="TURBULENCE", location=(0.0, 0.0, 2.4))
    turbulence = bpy.context.object
    turbulence.name = "Turbulence"
    turbulence.field.strength = 7.5
    turbulence.field.size = 1.5
    turbulence.field.noise = 1.8

    return wind, turbulence


def bake_cloth_to_shape_keys(scene, cloth, cloth_mod):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    frames = {}
    started = time.perf_counter()

    scene.frame_set(FRAME_START)
    depsgraph.update()
    for frame in range(FRAME_START, FRAME_END + 1):
        scene.frame_set(frame)
        depsgraph.update()
        eval_obj = cloth.evaluated_get(depsgraph)
        eval_mesh = eval_obj.to_mesh()
        frames[frame] = [tuple(v.co) for v in eval_mesh.vertices]
        eval_obj.to_mesh_clear()
        if frame % 12 == 0:
            print(f"CLOTH_SIM_FRAME={frame}")

    sim_seconds = time.perf_counter() - started

    basis = cloth.shape_key_add(name="Basis", from_mix=False)
    assert len(basis.data) == len(cloth.data.vertices)

    for frame in range(FRAME_START, FRAME_END + 1):
        key = cloth.shape_key_add(name=f"Sim_{frame:03d}", from_mix=False)
        coords = frames[frame]
        for idx, co in enumerate(coords):
            key.data[idx].co = co

        for f, value in ((frame - 1, 0.0), (frame, 1.0), (frame + 1, 0.0)):
            if f < FRAME_START:
                continue
            key.value = value
            key.keyframe_insert(data_path="value", frame=f)

    if cloth.data.shape_keys and cloth.data.shape_keys.animation_data:
        action = cloth.data.shape_keys.animation_data.action
        if action:
            for fc in action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"

    cloth.modifiers.remove(cloth_mod)
    scene.frame_set(FRAME_START)
    return sim_seconds, len(frames)


def add_render_modifiers(cloth):
    solid = cloth.modifiers.new(name="FabricThickness", type="SOLIDIFY")
    solid.thickness = 0.028
    solid.offset = 0.0

    sub = cloth.modifiers.new(name="RenderSubdivision", type="SUBSURF")
    sub.subdivision_type = "CATMULL_CLARK"
    sub.levels = 1
    sub.render_levels = 1


def setup_camera_and_lights(scene):
    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    camera.location = (7.6, -8.8, 6.7)
    camera_data.lens = 52.0
    look_at(camera, (0.0, 0.0, 2.15))

    def area(name, location, energy, size, color):
        data = bpy.data.lights.new(name=name, type="AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        data.color = color
        obj = bpy.data.objects.new(name, data)
        bpy.context.collection.objects.link(obj)
        obj.location = location
        look_at(obj, (0.0, 0.0, 2.0))

    area("Key", (1.5, -3.5, 7.5), 900.0, 5.0, (1.0, 0.86, 0.70))
    area("Fill", (-4.5, -1.0, 4.2), 430.0, 4.0, (0.45, 0.58, 1.0))
    area("Rim", (3.2, 4.0, 5.6), 620.0, 3.0, (1.0, 0.38, 0.18))


def build_scene() -> None:
    clear_scene()
    scene = bpy.context.scene
    engine = choose_engine(scene)
    samples = configure_render(scene)

    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.frame_current = FRAME_START
    scene.render.fps = FPS
    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False

    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.008, 0.010, 0.016, 1.0)
    bg.inputs["Strength"].default_value = 0.16

    cloth = make_grid_mesh("HammockCloth")
    cloth.data.materials.append(make_cloth_material())
    pin_group, pinned = make_pin_group(cloth)
    cloth_mod = add_cloth_modifier(cloth, pin_group)

    ball_a, ball_b = make_colliders()
    make_supports_and_ground()
    wind, turbulence = make_effectors()
    setup_camera_and_lights(scene)

    sim_seconds, baked_frames = bake_cloth_to_shape_keys(scene, cloth, cloth_mod)
    add_render_modifiers(cloth)

    report = {
        "experiment": "cloth-hammock-collision-eevee",
        "engine": engine,
        "frame_start": FRAME_START,
        "frame_end": FRAME_END,
        "fps": FPS,
        "resolution_x": RES_X,
        "resolution_y": RES_Y,
        "requested_render_samples": 16,
        "effective_render_samples": samples,
        "prepare_only": PREPARE_ONLY,
        "cloth": {
            "grid_x": GRID_X,
            "grid_y": GRID_Y,
            "vertex_count": len(cloth.data.vertices),
            "face_count": len(cloth.data.polygons),
            "pinned_vertex_count": len(pinned),
            "quality": 8,
            "self_collision": True,
            "baked_shape_keys": baked_frames,
            "shape_key_count": len(cloth.data.shape_keys.key_blocks) if cloth.data.shape_keys else 0,
            "simulation_seconds": round(sim_seconds, 3),
        },
        "colliders": [ball_a.name, ball_b.name],
        "effectors": [wind.name, turbulence.name],
        "render_modifiers": [m.type for m in cloth.modifiers],
        "blend": BLEND_PATH.name,
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

    print(f"BLENDER_ENGINE={engine}")
    print(f"CLOTH_VERTICES={len(cloth.data.vertices)}")
    print(f"CLOTH_BAKED_FRAMES={baked_frames}")
    print(f"CLOTH_SIM_SECONDS={sim_seconds:.3f}")
    print(f"BLEND_PATH={BLEND_PATH}")
    print(f"REPORT_PATH={REPORT_PATH}")


if __name__ == "__main__":
    build_scene()
