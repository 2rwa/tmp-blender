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

EXPERIMENT = "metaball-hidden-funnel-300-eevee"
BLEND_PATH = OUTPUT_DIR / f"{EXPERIMENT}.blend"
REPORT_PATH = OUTPUT_DIR / f"{EXPERIMENT}-report.json"

FRAME_START = 1
FRAME_END = 192
FPS = 24
RES_X = 480
RES_Y = 360
BALL_COUNT = 300
PREVIEW_FRAME = 144
PROXY_RADIUS = 0.095
META_RADIUS = 0.19
PREPARE_ONLY = os.environ.get("BLENDER_PREPARE_ONLY") == "1"


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.metaballs,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.curves,
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
        eevee.taa_render_samples = 20
        if hasattr(eevee, "use_gtao"):
            eevee.use_gtao = True
        if hasattr(eevee, "gtao_distance"):
            eevee.gtao_distance = 3.0
        if hasattr(eevee, "gtao_factor"):
            eevee.gtao_factor = 1.3
        return int(eevee.taa_render_samples)
    return None


def look_at(obj, target) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def make_material(name: str, color, roughness=0.5, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def make_mercury_material():
    mat = bpy.data.materials.new("HiddenFunnelMercury")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.04, 0.34, 0.43, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.88
    bsdf.inputs["Roughness"].default_value = 0.12
    return mat


def activate_only(obj) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def add_passive_rigidbody(obj, shape="MESH", friction=0.22, restitution=0.03) -> None:
    activate_only(obj)
    bpy.ops.rigidbody.object_add()
    rb = obj.rigid_body
    rb.type = "PASSIVE"
    rb.collision_shape = shape
    rb.friction = friction
    rb.restitution = restitution
    if hasattr(rb, "use_margin"):
        rb.use_margin = False


def make_open_frustum(name: str, z_top: float, z_bottom: float, r_top: float, r_bottom: float, segments=48):
    verts = []
    faces = []
    for z, radius in ((z_top, r_top), (z_bottom, r_bottom)):
        for i in range(segments):
            a = 2.0 * math.pi * i / segments
            verts.append((radius * math.cos(a), radius * math.sin(a), z))
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((i, j, segments + j, segments + i))

    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.hide_render = True
    add_passive_rigidbody(obj, shape="MESH", friction=0.18, restitution=0.02)
    return obj


def make_open_tube(name: str, z_top: float, z_bottom: float, radius: float, segments=40):
    return make_open_frustum(name, z_top, z_bottom, radius, radius, segments)


def make_receiver():
    dark = make_material("ReceiverDark", (0.022, 0.030, 0.038), roughness=0.26, metallic=0.72)
    floor_mat = make_material("GroundDark", (0.010, 0.014, 0.020), roughness=0.82, metallic=0.06)

    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=3.25, depth=0.24, location=(0.0, 0.0, 0.18))
    dish = bpy.context.object
    dish.name = "VisibleReceiver"
    dish.data.materials.append(dark)
    bevel = dish.modifiers.new(name="ReceiverBevel", type="BEVEL")
    bevel.width = 0.13
    bevel.segments = 4

    bpy.ops.mesh.primitive_torus_add(
        major_radius=2.85,
        minor_radius=0.18,
        major_segments=96,
        minor_segments=16,
        location=(0.0, 0.0, 0.53),
    )
    rim = bpy.context.object
    rim.name = "VisibleReceiverRim"
    rim.data.materials.append(dark)

    bpy.ops.mesh.primitive_plane_add(size=20.0, location=(0.0, 0.0, 0.0))
    ground = bpy.context.object
    ground.name = "Ground"
    ground.data.materials.append(floor_mat)

    # Physics receiver: invisible floor plus a ring of simple passive boxes.
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 0.44))
    catcher = bpy.context.object
    catcher.name = "HiddenReceiverFloor"
    catcher.scale = (2.8, 2.8, 0.06)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    catcher.hide_render = True
    add_passive_rigidbody(catcher, shape="BOX", friction=0.45, restitution=0.08)

    walls = []
    segments = 20
    radius = 2.92
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        bpy.ops.mesh.primitive_cube_add(
            size=1.0,
            location=(radius * math.cos(a), radius * math.sin(a), 0.92),
        )
        wall = bpy.context.object
        wall.name = f"HiddenReceiverWall_{i:02d}"
        wall.dimensions = (0.28, 1.05, 1.05)
        wall.rotation_euler[2] = a + math.pi / 2.0
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        wall.hide_render = True
        add_passive_rigidbody(wall, shape="BOX", friction=0.30, restitution=0.06)
        walls.append(wall)
    return dish, catcher, walls


def ensure_rigidbody_world(scene):
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    world = scene.rigidbody_world
    world.point_cache.frame_start = FRAME_START
    world.point_cache.frame_end = FRAME_END
    world.substeps_per_frame = 8
    world.solver_iterations = 24
    return world


def make_proxy_bodies():
    # One shared low-poly sphere mesh keeps the 300 physics proxies cheap.
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=PROXY_RADIUS, location=(0.0, 0.0, -20.0))
    template = bpy.context.object
    template.name = "ProxyTemplate"
    template.hide_render = True
    shared_mesh = template.data

    bodies = []
    cols = 10
    rows = 10
    layers = 3
    spacing = 0.245
    release_span = 84

    for index in range(BALL_COUNT):
        if index == 0:
            obj = template
        else:
            obj = bpy.data.objects.new(f"Proxy_{index:03d}", shared_mesh)
            bpy.context.collection.objects.link(obj)

        layer = index // (cols * rows)
        rem = index % (cols * rows)
        iy = rem // cols
        ix = rem % cols

        x = (ix - (cols - 1) / 2.0) * spacing
        y = (iy - (rows - 1) / 2.0) * spacing
        z = 8.25 + layer * 0.33 + 0.035 * ((index * 17) % 5)
        obj.location = (x, y, z)
        obj.name = f"Proxy_{index:03d}"
        obj.hide_render = True

        activate_only(obj)
        bpy.ops.rigidbody.object_add()
        rb = obj.rigid_body
        rb.type = "ACTIVE"
        rb.mass = 0.035
        rb.friction = 0.20
        rb.restitution = 0.08
        rb.linear_damping = 0.03
        rb.angular_damping = 0.05
        rb.collision_shape = "SPHERE"
        rb.use_deactivation = False

        release = 1 + (index * 17) % release_span
        rb.kinematic = True
        rb.keyframe_insert(data_path="kinematic", frame=FRAME_START)
        if release > FRAME_START:
            rb.keyframe_insert(data_path="kinematic", frame=release - 1)
        rb.kinematic = False
        rb.keyframe_insert(data_path="kinematic", frame=release)

        bodies.append((obj, release))

    for obj, _release in bodies:
        if obj.animation_data and obj.animation_data.action:
            for fc in obj.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "CONSTANT"

    return bodies


def simulate_and_sample(scene, bodies):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    samples = {obj.name: {} for obj, _ in bodies}
    first_exit = {}
    started = time.perf_counter()

    scene.frame_set(FRAME_START)
    depsgraph.update()

    for frame in range(FRAME_START, FRAME_END + 1):
        scene.frame_set(frame)
        depsgraph.update()

        for obj, release in bodies:
            eval_obj = obj.evaluated_get(depsgraph)
            loc = eval_obj.matrix_world.translation.copy()
            samples[obj.name][frame] = tuple(loc)

            if frame >= release and obj.name not in first_exit and loc.z < 2.25:
                first_exit[obj.name] = frame

        if frame % 12 == 0:
            exited = sum(1 for name in samples if name in first_exit)
            print(f"HIDDEN_FUNNEL_SIM_FRAME={frame}", flush=True)
            print(f"HIDDEN_FUNNEL_EXITED={exited}", flush=True)

    seconds = time.perf_counter() - started

    final_positions = [Vector(samples[obj.name][FRAME_END]) for obj, _ in bodies]
    in_dish = sum(
        1 for p in final_positions
        if p.z < 1.55 and math.hypot(p.x, p.y) < 3.0
    )
    leaked = sum(1 for p in final_positions if p.z < -1.0)
    exited = len(first_exit)
    exit_frames = list(first_exit.values())

    return samples, {
        "simulation_seconds": round(seconds, 3),
        "exited_count": exited,
        "first_exit_frame": min(exit_frames) if exit_frames else None,
        "last_exit_frame": max(exit_frames) if exit_frames else None,
        "in_dish_final": in_dish,
        "leaked_below_world": leaked,
    }


def make_metaballs_from_samples(samples, bodies):
    meta = bpy.data.metaballs.new("HiddenFunnelMetaballs")
    meta.resolution = 0.13
    meta.render_resolution = 0.08
    meta.threshold = 0.62

    obj = bpy.data.objects.new("HiddenFunnelMetaballs", meta)
    bpy.context.collection.objects.link(obj)
    meta.materials.append(make_mercury_material())

    for body, release in bodies:
        element = meta.elements.new(type="BALL")
        element.stiffness = 2.0
        element.radius = 0.001
        element.co = samples[body.name][FRAME_START]

        element.keyframe_insert(data_path="co", frame=FRAME_START)
        element.keyframe_insert(data_path="radius", frame=FRAME_START)
        if release > FRAME_START:
            element.co = samples[body.name][release - 1]
            element.radius = 0.001
            element.keyframe_insert(data_path="co", frame=release - 1)
            element.keyframe_insert(data_path="radius", frame=release - 1)

        element.radius = META_RADIUS
        for frame in range(release, FRAME_END + 1):
            element.co = samples[body.name][frame]
            element.keyframe_insert(data_path="co", frame=frame)
        element.keyframe_insert(data_path="radius", frame=release)

    if meta.animation_data and meta.animation_data.action:
        for fc in meta.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"

    return obj, meta


def remove_physics_helpers(bodies, funnel, tube, receiver_floor, receiver_walls):
    for obj, _release in bodies:
        bpy.data.objects.remove(obj, do_unlink=True)
    for obj in [funnel, tube, receiver_floor, *receiver_walls]:
        if obj and obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)


def setup_camera_and_lights(scene):
    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera

    shots = [
        (1, (8.8, -12.0, 7.2), (0.0, 0.0, 4.0), 52.0),
        (72, (8.2, -10.8, 6.5), (0.0, 0.0, 3.5), 55.0),
        (144, (7.1, -9.2, 5.2), (0.0, 0.0, 2.0), 57.0),
        (192, (7.6, -9.6, 5.4), (0.0, 0.0, 1.5), 55.0),
    ]
    for frame, location, target, lens in shots:
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
        look_at(obj, (0.0, 0.0, 2.5))

    area("Key", (-4.5, -5.0, 9.0), 1250.0, 5.5, (0.68, 0.95, 1.0))
    area("Fill", (5.0, -2.0, 6.2), 720.0, 4.5, (0.30, 0.62, 1.0))
    area("Rim", (2.0, 4.5, 7.2), 980.0, 3.2, (1.0, 0.38, 0.15))


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
    scene.render.image_settings.file_format = "PNG"

    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.003, 0.005, 0.009, 1.0)
    bg.inputs["Strength"].default_value = 0.10

    ensure_rigidbody_world(scene)

    # These two colliders do the trick but never render.
    funnel = make_open_frustum("HiddenFunnel", 7.30, 4.65, 2.35, 0.46, segments=48)
    tube = make_open_tube("HiddenTube", 4.70, 2.20, 0.47, segments=40)

    _dish, receiver_floor, receiver_walls = make_receiver()
    bodies = make_proxy_bodies()
    setup_camera_and_lights(scene)

    position_samples, physics = simulate_and_sample(scene, bodies)
    meta_obj, meta = make_metaballs_from_samples(position_samples, bodies)

    action = meta.animation_data.action if meta.animation_data else None
    fcurve_count = len(action.fcurves) if action else 0
    keyframe_points = sum(len(fc.keyframe_points) for fc in action.fcurves) if action else 0

    # Rendering uses only the baked metaballs. Physics helpers are intentionally invisible
    # in the concept, so remove them completely after sampling.
    remove_physics_helpers(bodies, funnel, tube, receiver_floor, receiver_walls)
    scene.frame_set(FRAME_START)

    report = {
        "experiment": EXPERIMENT,
        "engine": engine,
        "frame_start": FRAME_START,
        "frame_end": FRAME_END,
        "fps": FPS,
        "resolution_x": RES_X,
        "resolution_y": RES_Y,
        "requested_render_samples": 20,
        "effective_render_samples": samples,
        "metaball": {
            "object": meta_obj.name,
            "element_count": len(meta.elements),
            "resolution": meta.resolution,
            "render_resolution": meta.render_resolution,
            "threshold": meta.threshold,
            "fcurve_count": fcurve_count,
            "keyframe_points": keyframe_points,
            "radius": META_RADIUS,
        },
        "physics": {
            "proxy_count": BALL_COUNT,
            "proxy_radius": PROXY_RADIUS,
            "rigid_substeps_per_frame": 8,
            "solver_iterations": 24,
            "hidden_funnel": True,
            "hidden_tube": True,
            **physics,
        },
        "blend": BLEND_PATH.name,
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

    print(f"BLENDER_ENGINE={engine}")
    print(f"METABALL_ELEMENTS={len(meta.elements)}")
    print(f"METABALL_KEYFRAME_POINTS={keyframe_points}")
    print(f"PHYSICS_SECONDS={physics['simulation_seconds']}")
    print(f"EXITED_COUNT={physics['exited_count']}")
    print(f"IN_DISH_FINAL={physics['in_dish_final']}")
    print(f"LEAKED_BELOW_WORLD={physics['leaked_below_world']}")
    print(f"BLEND_PATH={BLEND_PATH}")
    print(f"REPORT_PATH={REPORT_PATH}")


if __name__ == "__main__":
    build_scene()
