from __future__ import annotations

import json
import math
import os
import random
import time
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path.cwd()
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BLEND_PATH = OUTPUT_DIR / "cloth-hammock-rigidbody-drop-eevee.blend"
REPORT_PATH = OUTPUT_DIR / "cloth-hammock-rigidbody-drop-eevee-report.json"

FRAME_START = 1
FRAME_END = 192
FPS = 24
RES_X = 480
RES_Y = 360
PREPARE_ONLY = os.environ.get("BLENDER_PREPARE_ONLY") == "1"

GRID_X = 45
GRID_Y = 35
WIDTH = 5.6
DEPTH = 4.2
CLOTH_Z = 2.8

BALL_COUNT = 12
BALL_START_FRAME = 18
BALL_STAGGER = 7
RIGID_SEED = 42


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


def ensure_rigidbody_world(scene):
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    world = scene.rigidbody_world
    world.point_cache.frame_start = FRAME_START
    world.point_cache.frame_end = FRAME_END
    world.substeps_per_frame = 5
    world.solver_iterations = 25
    return world


def make_rigid_proxy():
    proxy_mat = make_material("RigidProxy", (0.02, 0.02, 0.025), roughness=0.9, metallic=0.0)
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=48,
        ring_count=24,
        radius=1.0,
        location=(0.0, 0.0, 0.95),
        scale=(3.05, 2.35, 1.25),
    )
    proxy = bpy.context.object
    proxy.name = "RigidHammockProxy"
    proxy.data.materials.append(proxy_mat)
    proxy.hide_render = True
    bpy.ops.rigidbody.object_add()
    proxy.rigid_body.type = "PASSIVE"
    proxy.rigid_body.collision_shape = "MESH"
    proxy.rigid_body.friction = 0.78
    proxy.rigid_body.restitution = 0.04
    return proxy


def make_rigid_bodies():
    random.seed(RIGID_SEED)
    palette = [
        (0.78, 0.14, 0.12),
        (0.10, 0.48, 0.86),
        (0.88, 0.68, 0.16),
        (0.22, 0.70, 0.28),
        (0.72, 0.22, 0.74),
        (0.85, 0.42, 0.14),
    ]
    bodies = []
    cols = 4
    for idx in range(BALL_COUNT):
        row = idx // cols
        col = idx % cols
        radius = 0.25 + 0.035 * (idx % 3) + random.uniform(-0.012, 0.018)
        x = -1.35 + col * 0.9 + random.uniform(-0.08, 0.08)
        y = -0.9 + row * 0.9 + random.uniform(-0.08, 0.08)
        z = 5.25 + row * 0.72 + random.uniform(-0.05, 0.16)

        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=24,
            ring_count=14,
            radius=radius,
            location=(x, y, z),
        )
        obj = bpy.context.object
        obj.name = f"RigidBall_{idx:02d}"
        obj.data.materials.append(
            make_material(
                f"RigidBallMat_{idx:02d}",
                palette[idx % len(palette)],
                roughness=0.28,
                metallic=0.30,
            )
        )

        # Collision modifier makes the moving rigid body visible to the Cloth solver.
        add_collision(obj, friction=9.0, thickness=0.025)

        bpy.ops.rigidbody.object_add()
        rb = obj.rigid_body
        rb.type = "ACTIVE"
        rb.mass = 0.75 + radius * 1.8
        rb.friction = 0.68
        rb.restitution = 0.10
        rb.linear_damping = 0.05
        rb.angular_damping = 0.08
        rb.collision_shape = "SPHERE"
        rb.use_deactivation = False

        # Stagger release times using rigid-body kinematic animation.
        release = BALL_START_FRAME + idx * BALL_STAGGER
        rb.kinematic = True
        rb.keyframe_insert(data_path="kinematic", frame=1)
        rb.keyframe_insert(data_path="kinematic", frame=max(1, release - 1))
        rb.kinematic = False
        rb.keyframe_insert(data_path="kinematic", frame=release)
        rb.keyframe_insert(data_path="kinematic", frame=FRAME_END)

        bodies.append(obj)
    return bodies


def make_supports_and_ground():
    dark = make_material("Supports", (0.025, 0.028, 0.034), roughness=0.4, metallic=0.72)
    ground_mat = make_material("Ground", (0.018, 0.02, 0.026), roughness=0.88, metallic=0.02)

    bpy.ops.mesh.primitive_plane_add(size=16.0, location=(0.0, 0.0, -0.02))
    ground = bpy.context.object
    ground.name = "Ground"
    ground.data.materials.append(ground_mat)
    bpy.context.view_layer.objects.active = ground
    bpy.ops.rigidbody.object_add()
    ground.rigid_body.type = "PASSIVE"
    ground.rigid_body.friction = 0.8

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
    wind.field.strength = 520.0
    wind.field.noise = 1.4
    for frame, angle in ((1, -8.0), (52, 5.0), (96, 18.0), (144, -14.0), (192, 9.0)):
        wind.rotation_euler = (0.0, math.radians(90.0), math.radians(angle))
        wind.keyframe_insert(data_path="rotation_euler", frame=frame)

    bpy.ops.object.effector_add(type="TURBULENCE", location=(0.0, 0.0, 2.4))
    turbulence = bpy.context.object
    turbulence.name = "Turbulence"
    turbulence.field.strength = 7.5
    turbulence.field.size = 1.5
    turbulence.field.noise = 1.8
    for frame, location in (
        (1, (-1.4, -1.0, 2.2)),
        (72, (0.5, -0.3, 2.6)),
        (132, (1.25, 0.9, 2.1)),
        (192, (-0.4, 1.0, 2.5)),
    ):
        turbulence.location = location
        turbulence.keyframe_insert(data_path="location", frame=frame)

    return wind, turbulence


def bake_simulation_to_keys(scene, cloth, cloth_mod, rigid_objects):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    cloth_frames = {}
    rigid_frames = {obj.name: {} for obj in rigid_objects}
    started = time.perf_counter()

    scene.frame_set(FRAME_START)
    depsgraph.update()

    # Run both solvers in one strictly sequential pass. This avoids
    # context-sensitive rigid-body bake operators and guarantees the cloth
    # samples the same rigid-body motion that we later persist.
    for frame in range(FRAME_START, FRAME_END + 1):
        scene.frame_set(frame)
        depsgraph.update()

        eval_cloth = cloth.evaluated_get(depsgraph)
        eval_mesh = eval_cloth.to_mesh()
        cloth_frames[frame] = [tuple(v.co) for v in eval_mesh.vertices]
        eval_cloth.to_mesh_clear()

        for obj in rigid_objects:
            eval_obj = obj.evaluated_get(depsgraph)
            loc, rot, scale = eval_obj.matrix_world.decompose()
            rigid_frames[obj.name][frame] = (
                tuple(loc),
                tuple(rot),
                tuple(scale),
            )

        if frame % 12 == 0:
            print(f"HYBRID_SIM_FRAME={frame}")

    simulation_seconds = time.perf_counter() - started

    # Persist cloth deformation as one shape key per frame.
    basis = cloth.shape_key_add(name="Basis", from_mix=False)
    assert len(basis.data) == len(cloth.data.vertices)

    for frame in range(FRAME_START, FRAME_END + 1):
        key = cloth.shape_key_add(name=f"Sim_{frame:03d}", from_mix=False)
        coords = cloth_frames[frame]
        for idx, co in enumerate(coords):
            key.data[idx].co = co

        for key_frame, value in (
            (frame - 1, 0.0),
            (frame, 1.0),
            (frame + 1, 0.0),
        ):
            if key_frame < FRAME_START:
                continue
            key.value = value
            key.keyframe_insert(data_path="value", frame=key_frame)

    if cloth.data.shape_keys and cloth.data.shape_keys.animation_data:
        action = cloth.data.shape_keys.animation_data.action
        if action:
            for fc in action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"

    cloth.modifiers.remove(cloth_mod)

    # Persist evaluated rigid-body transforms without bpy.ops.rigidbody.
    rigid_bake_started = time.perf_counter()
    for obj in rigid_objects:
        # Remove the release-time kinematic F-curves used during simulation.
        if obj.animation_data and obj.animation_data.action:
            action = obj.animation_data.action
            for fc in list(action.fcurves):
                if fc.data_path == "rigid_body.kinematic":
                    action.fcurves.remove(fc)

        obj.rotation_mode = "QUATERNION"
        if obj.rigid_body:
            obj.rigid_body.kinematic = True

        for frame in range(FRAME_START, FRAME_END + 1):
            loc, rot, scale = rigid_frames[obj.name][frame]
            obj.location = loc
            obj.rotation_quaternion = rot
            obj.scale = scale
            obj.keyframe_insert(data_path="location", frame=frame)
            obj.keyframe_insert(data_path="rotation_quaternion", frame=frame)
            obj.keyframe_insert(data_path="scale", frame=frame)

        if obj.animation_data and obj.animation_data.action:
            for fc in obj.animation_data.action.fcurves:
                if fc.data_path in {"location", "rotation_quaternion", "scale"}:
                    for kp in fc.keyframe_points:
                        kp.interpolation = "LINEAR"

    rigid_bake_seconds = time.perf_counter() - rigid_bake_started
    scene.frame_set(FRAME_START)
    return simulation_seconds, len(cloth_frames), rigid_bake_seconds

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

    camera_shots = [
        (1, (8.1, -9.4, 6.9), (0.0, 0.0, 2.10), 54.0),
        (58, (7.0, -8.1, 5.8), (0.2, 0.0, 2.15), 56.0),
        (108, (5.8, -7.0, 4.8), (0.5, 0.25, 2.10), 59.0),
        (152, (6.2, -5.6, 4.5), (-0.2, 0.25, 2.05), 61.0),
        (192, (7.8, -6.8, 5.8), (0.0, 0.0, 2.15), 55.0),
    ]
    for frame, location, target, lens in camera_shots:
        camera.location = location
        camera_data.lens = lens
        look_at(camera, target)
        camera.keyframe_insert(data_path="location", frame=frame)
        camera.keyframe_insert(data_path="rotation_euler", frame=frame)
        camera_data.keyframe_insert(data_path="lens", frame=frame)

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

    make_supports_and_ground()
    wind, turbulence = make_effectors()
    ensure_rigidbody_world(scene)
    rigid_proxy = make_rigid_proxy()
    rigid_bodies = make_rigid_bodies()
    setup_camera_and_lights(scene)

    # Advancing the cloth simulation also advances the rigid-body world.
    sim_seconds, baked_frames, rigid_seconds = bake_simulation_to_keys(
        scene,
        cloth,
        cloth_mod,
        rigid_bodies,
    )
    add_render_modifiers(cloth)

    report = {
        "experiment": "cloth-hammock-rigidbody-drop-eevee",
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
        "rigid_bodies": {
            "count": len(rigid_bodies),
            "names": [obj.name for obj in rigid_bodies],
            "bake_seconds": round(rigid_seconds, 3),
            "proxy": rigid_proxy.name,
            "stagger_frames": BALL_STAGGER,
        },
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
    print(f"RIGID_BODY_COUNT={len(rigid_bodies)}")
    print(f"RIGID_BODY_BAKE_SECONDS={rigid_seconds:.3f}")
    print(f"BLEND_PATH={BLEND_PATH}")
    print(f"REPORT_PATH={REPORT_PATH}")


if __name__ == "__main__":
    build_scene()
