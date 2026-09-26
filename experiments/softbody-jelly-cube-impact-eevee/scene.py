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

EXPERIMENT = "softbody-jelly-cube-impact-eevee"
BLEND_PATH = OUTPUT_DIR / f"{EXPERIMENT}.blend"
REPORT_PATH = OUTPUT_DIR / f"{EXPERIMENT}-report.json"

FRAME_START = 1
FRAME_END = 144
FPS = 24
RES_X = 480
RES_Y = 360
PREPARE_ONLY = os.environ.get("BLENDER_PREPARE_ONLY") == "1"


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
        eevee.taa_render_samples = 24
        if hasattr(eevee, "use_gtao"):
            eevee.use_gtao = True
        if hasattr(eevee, "gtao_distance"):
            eevee.gtao_distance = 3.0
        if hasattr(eevee, "gtao_factor"):
            eevee.gtao_factor = 1.35
        return int(eevee.taa_render_samples)
    return None


def look_at(obj, target) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def set_bsdf_input(bsdf, names, value) -> bool:
    for name in names:
        socket = bsdf.inputs.get(name)
        if socket is not None:
            socket.default_value = value
            return True
    return False


def make_simple_material(name: str, color, roughness=0.5, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def make_jelly_material():
    mat = bpy.data.materials.new("JellyMaterial")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.12, 0.72, 0.42, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.18
    bsdf.inputs["Metallic"].default_value = 0.0
    set_bsdf_input(bsdf, ("IOR",), 1.36)
    set_bsdf_input(bsdf, ("Transmission Weight", "Transmission"), 0.32)
    set_bsdf_input(bsdf, ("Subsurface Weight", "Subsurface"), 0.12)

    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 3.2
    noise.inputs["Detail"].default_value = 2.0
    noise.inputs["Roughness"].default_value = 0.58

    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (0.035, 0.24, 0.11, 1.0)
    ramp.color_ramp.elements[1].position = 0.82
    ramp.color_ramp.elements[1].color = (0.30, 1.0, 0.62, 1.0)

    texcoord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (0.8, 0.8, 1.15)

    links.new(texcoord.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def active(obj) -> None:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)


def make_rounded_jelly():
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 1.72))
    jelly = bpy.context.object
    jelly.name = "JellyCube"
    jelly.scale = (1.55, 1.32, 1.42)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    bevel = jelly.modifiers.new(name="RoundedCorners", type="BEVEL")
    bevel.width = 0.28
    bevel.segments = 5
    bevel.limit_method = "ANGLE"
    active(jelly)
    bpy.ops.object.modifier_apply(modifier=bevel.name)

    sub = jelly.modifiers.new(name="PhysicsSubdivision", type="SUBSURF")
    sub.subdivision_type = "CATMULL_CLARK"
    sub.levels = 1
    sub.render_levels = 1
    bpy.ops.object.modifier_apply(modifier=sub.name)

    for poly in jelly.data.polygons:
        poly.use_smooth = True

    jelly.data.materials.append(make_jelly_material())
    return jelly


def add_softbody(jelly):
    mod = jelly.modifiers.new(name="JellySoftBody", type="SOFT_BODY")
    settings = mod.settings
    settings.use_edges = True
    settings.use_stiff_quads = True
    settings.pull = 0.58
    settings.push = 0.58
    settings.shear = 0.52
    settings.bend = 2.2
    settings.damping = 4.5
    settings.friction = 1.8
    settings.mass = 1.1
    settings.speed = 1.0
    settings.gravity = 0.30
    settings.plastic = 0

    settings.use_goal = True
    settings.goal_default = 0.17
    settings.goal_spring = 0.34
    settings.goal_friction = 3.2
    settings.goal_min = 0.0
    settings.goal_max = 1.0

    settings.use_edge_collision = True
    settings.use_face_collision = True
    settings.use_self_collision = False
    settings.use_auto_step = True
    settings.step_min = 2
    settings.step_max = 18
    settings.error_threshold = 0.02

    cache = mod.point_cache
    cache.frame_start = FRAME_START
    cache.frame_end = FRAME_END
    cache.frame_step = 1
    return mod


def add_collision(obj, thickness=0.035, damping=0.15) -> None:
    obj.modifiers.new(name="Collision", type="COLLISION")
    obj.collision.use = True
    if hasattr(obj.collision, "thickness_outer"):
        obj.collision.thickness_outer = thickness
    if hasattr(obj.collision, "damping"):
        obj.collision.damping = damping


def keyframe_linear(obj, data_path: str) -> None:
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            if fc.data_path == data_path:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"


def make_projectile():
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=48,
        ring_count=24,
        radius=0.58,
        location=(-6.5, -0.16, 1.92),
    )
    ball = bpy.context.object
    ball.name = "ImpactSphere"
    ball.data.materials.append(
        make_simple_material("ImpactMetal", (0.11, 0.13, 0.16), roughness=0.16, metallic=0.92)
    )
    for poly in ball.data.polygons:
        poly.use_smooth = True

    add_collision(ball, thickness=0.055, damping=0.08)

    path = [
        (1, (-6.5, -0.16, 1.92)),
        (34, (-4.8, -0.16, 1.92)),
        (48, (-2.65, -0.16, 1.92)),
        (58, (-1.25, -0.16, 1.92)),
        (68, (0.55, -0.16, 1.92)),
        (82, (3.25, -0.16, 1.92)),
        (110, (5.4, -0.16, 1.92)),
        (144, (6.4, -0.16, 1.92)),
    ]
    for frame, location in path:
        ball.location = location
        ball.keyframe_insert(data_path="location", frame=frame)
    keyframe_linear(ball, "location")
    return ball, path


def make_floor_and_stage():
    floor_mat = make_simple_material("Floor", (0.018, 0.022, 0.028), roughness=0.82, metallic=0.05)
    rim_mat = make_simple_material("StageRim", (0.055, 0.060, 0.072), roughness=0.35, metallic=0.62)

    bpy.ops.mesh.primitive_plane_add(size=18.0, location=(0.0, 0.0, 0.0))
    floor = bpy.context.object
    floor.name = "Ground"
    floor.data.materials.append(floor_mat)
    add_collision(floor, thickness=0.04, damping=0.35)

    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 0.11))
    plinth = bpy.context.object
    plinth.name = "JellyPlinth"
    plinth.scale = (2.05, 1.80, 0.10)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    plinth.data.materials.append(rim_mat)
    add_collision(plinth, thickness=0.025, damping=0.30)
    return floor, plinth


def bake_softbody_to_shape_keys(scene, jelly, soft_mod):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    basis_coords = [tuple(v.co) for v in jelly.data.vertices]
    frames = {}
    max_displacement = 0.0
    max_displacement_frame = FRAME_START
    started = time.perf_counter()

    scene.frame_set(FRAME_START)
    depsgraph.update()

    for frame in range(FRAME_START, FRAME_END + 1):
        scene.frame_set(frame)
        depsgraph.update()

        eval_obj = jelly.evaluated_get(depsgraph)
        eval_mesh = eval_obj.to_mesh()
        if len(eval_mesh.vertices) != len(basis_coords):
            raise RuntimeError(
                f"soft-body topology changed at frame {frame}: "
                f"{len(eval_mesh.vertices)} != {len(basis_coords)}"
            )

        coords = [tuple(v.co) for v in eval_mesh.vertices]
        frames[frame] = coords

        frame_max = 0.0
        for base, co in zip(basis_coords, coords):
            dx = co[0] - base[0]
            dy = co[1] - base[1]
            dz = co[2] - base[2]
            disp = math.sqrt(dx * dx + dy * dy + dz * dz)
            if disp > frame_max:
                frame_max = disp

        if frame_max > max_displacement:
            max_displacement = frame_max
            max_displacement_frame = frame

        eval_obj.to_mesh_clear()

        if frame % 12 == 0:
            print(f"SOFTBODY_SIM_FRAME={frame}")
            print(f"SOFTBODY_FRAME_MAX_DISPLACEMENT={frame_max:.6f}")

    simulation_seconds = time.perf_counter() - started

    jelly.modifiers.remove(soft_mod)
    basis = jelly.shape_key_add(name="Basis", from_mix=False)
    assert len(basis.data) == len(basis_coords)

    for frame in range(FRAME_START, FRAME_END + 1):
        key = jelly.shape_key_add(name=f"Sim_{frame:03d}", from_mix=False)
        coords = frames[frame]
        for idx, co in enumerate(coords):
            key.data[idx].co = co

        for key_frame, value in ((frame - 1, 0.0), (frame, 1.0), (frame + 1, 0.0)):
            if key_frame < FRAME_START or key_frame > FRAME_END:
                continue
            key.value = value
            key.keyframe_insert(data_path="value", frame=key_frame)

    if jelly.data.shape_keys and jelly.data.shape_keys.animation_data:
        action = jelly.data.shape_keys.animation_data.action
        if action:
            for fc in action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = "LINEAR"

    scene.frame_set(FRAME_START)
    return {
        "simulation_seconds": round(simulation_seconds, 3),
        "baked_frames": len(frames),
        "max_displacement": round(max_displacement, 6),
        "max_displacement_frame": max_displacement_frame,
    }


def add_render_modifiers(jelly):
    sub = jelly.modifiers.new(name="RenderSubdivision", type="SUBSURF")
    sub.subdivision_type = "CATMULL_CLARK"
    sub.levels = 1
    sub.render_levels = 1


def setup_camera_and_lights(scene):
    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera

    shots = [
        (1, (7.6, -10.0, 5.6), (0.0, 0.0, 1.72), 52.0),
        (58, (7.0, -9.0, 5.2), (0.0, -0.05, 1.72), 55.0),
        (92, (6.5, -8.2, 4.9), (0.25, -0.05, 1.72), 57.0),
        (144, (7.3, -8.9, 5.4), (0.0, 0.0, 1.72), 54.0),
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
        look_at(obj, (0.0, 0.0, 1.7))
        return obj

    area("Key", (-3.0, -4.0, 7.5), 980.0, 5.0, (0.82, 1.0, 0.88))
    area("Fill", (4.5, -2.0, 4.8), 520.0, 4.0, (0.40, 0.58, 1.0))
    area("Rim", (2.0, 4.0, 6.4), 760.0, 3.0, (0.95, 0.36, 0.16))

    bpy.ops.object.light_add(type="AREA", location=(-0.5, 1.6, 1.7))
    back = bpy.context.object
    back.name = "GelBacklight"
    back.data.energy = 460.0
    back.data.shape = "RECTANGLE"
    back.data.size = 2.4
    back.data.size_y = 2.4
    back.data.color = (0.38, 1.0, 0.58)
    look_at(back, (0.0, 0.0, 1.7))


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
    scene.render.film_transparent = False

    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.004, 0.006, 0.010, 1.0)
    bg.inputs["Strength"].default_value = 0.12

    make_floor_and_stage()
    jelly = make_rounded_jelly()
    projectile, projectile_path = make_projectile()
    soft_mod = add_softbody(jelly)
    setup_camera_and_lights(scene)

    bake = bake_softbody_to_shape_keys(scene, jelly, soft_mod)
    add_render_modifiers(jelly)

    report = {
        "experiment": EXPERIMENT,
        "engine": engine,
        "frame_start": FRAME_START,
        "frame_end": FRAME_END,
        "fps": FPS,
        "resolution_x": RES_X,
        "resolution_y": RES_Y,
        "requested_render_samples": 24,
        "effective_render_samples": samples,
        "prepare_only": PREPARE_ONLY,
        "jelly": {
            "vertex_count": len(jelly.data.vertices),
            "face_count": len(jelly.data.polygons),
            "baked_shape_keys": bake["baked_frames"],
            "shape_key_count": len(jelly.data.shape_keys.key_blocks) if jelly.data.shape_keys else 0,
            "simulation_seconds": bake["simulation_seconds"],
            "max_displacement": bake["max_displacement"],
            "max_displacement_frame": bake["max_displacement_frame"],
            "goal_default": 0.17,
            "goal_spring": 0.34,
            "goal_friction": 3.2,
            "pull": 0.58,
            "push": 0.58,
            "bend": 2.2,
        },
        "projectile": {
            "name": projectile.name,
            "radius": 0.58,
            "path": [{"frame": frame, "location": list(location)} for frame, location in projectile_path],
            "keyframes": len(projectile_path),
        },
        "render_modifiers": [m.type for m in jelly.modifiers],
        "blend": BLEND_PATH.name,
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

    print(f"BLENDER_ENGINE={engine}")
    print(f"JELLY_VERTICES={len(jelly.data.vertices)}")
    print(f"JELLY_BAKED_FRAMES={bake['baked_frames']}")
    print(f"JELLY_SIM_SECONDS={bake['simulation_seconds']:.3f}")
    print(f"JELLY_MAX_DISPLACEMENT={bake['max_displacement']:.6f}")
    print(f"JELLY_MAX_DISPLACEMENT_FRAME={bake['max_displacement_frame']}")
    print(f"PROJECTILE_KEYFRAMES={len(projectile_path)}")
    print(f"BLEND_PATH={BLEND_PATH}")
    print(f"REPORT_PATH={REPORT_PATH}")


if __name__ == "__main__":
    build_scene()
