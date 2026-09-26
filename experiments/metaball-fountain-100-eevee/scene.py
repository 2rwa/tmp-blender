from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path.cwd()
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

EXPERIMENT = "metaball-fountain-100-eevee"
BLEND_PATH = OUTPUT_DIR / f"{EXPERIMENT}.blend"
REPORT_PATH = OUTPUT_DIR / f"{EXPERIMENT}-report.json"

FRAME_START = 1
FRAME_END = 144
FPS = 24
RES_X = 480
RES_Y = 360
ELEMENT_COUNT = 100
PREVIEW_FRAME = 108


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.metaballs,
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
    mat = bpy.data.materials.new("MetaballMercury")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.06, 0.32, 0.38, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.82
    bsdf.inputs["Roughness"].default_value = 0.14
    return mat


def simulate_particle(index: int):
    spawn = 1 + (index * 7) % 72
    golden = 2.399963229728653
    angle = index * golden

    radial_speed = 1.45 + 0.55 * ((index * 17) % 11) / 10.0
    vz = 6.1 + 1.45 * ((index * 13) % 13) / 12.0
    vx = radial_speed * math.cos(angle)
    vy = radial_speed * math.sin(angle)

    p = Vector((0.0, 0.0, 1.05))
    v = Vector((vx, vy, vz))
    dt = 1.0 / FPS
    radius = 0.23 + 0.085 * ((index * 19) % 9) / 8.0
    positions = {}
    bounce_count = 0

    for frame in range(spawn, FRAME_END + 1):
        age = frame - spawn
        swirl = 0.055 * math.sin(0.18 * age + index * 0.31)
        v.x += -p.y * swirl * dt
        v.y += p.x * swirl * dt
        v.z -= 9.81 * dt
        p += v * dt

        radial = math.hypot(p.x, p.y)
        basin_limit = 3.15
        if radial > basin_limit:
            nx, ny = p.x / radial, p.y / radial
            p.x = nx * basin_limit
            p.y = ny * basin_limit
            dot = v.x * nx + v.y * ny
            if dot > 0.0:
                v.x -= 1.65 * dot * nx
                v.y -= 1.65 * dot * ny
            v.x *= 0.78
            v.y *= 0.78

        if p.z < 0.48:
            p.z = 0.48
            if abs(v.z) > 0.55:
                v.z = -v.z * 0.31
                bounce_count += 1
            else:
                v.z = 0.0
            v.x *= 0.86
            v.y *= 0.86

        if p.z <= 0.481 and abs(v.z) < 0.12:
            v.x *= 0.965
            v.y *= 0.965

        positions[frame] = tuple(p)

    return {
        "spawn": spawn,
        "radius": radius,
        "positions": positions,
        "bounce_count": bounce_count,
    }


def build_trajectories():
    trajectories = [simulate_particle(i) for i in range(ELEMENT_COUNT)]
    max_height = max(
        p[2]
        for item in trajectories
        for p in item["positions"].values()
    )
    total_bounces = sum(item["bounce_count"] for item in trajectories)
    return trajectories, max_height, total_bounces


def make_metaball_fountain(trajectories):
    meta = bpy.data.metaballs.new("MetaballFountain")
    meta.resolution = 0.12
    meta.render_resolution = 0.075
    meta.threshold = 0.62

    obj = bpy.data.objects.new("MetaballFountain", meta)
    bpy.context.collection.objects.link(obj)
    meta.materials.append(make_mercury_material())

    for index, item in enumerate(trajectories):
        element = meta.elements.new(type="BALL")
        element.stiffness = 2.0
        element.radius = 0.001
        element.co = (0.0, 0.0, 1.05)

        spawn = item["spawn"]
        if spawn > FRAME_START:
            element.keyframe_insert(data_path="co", frame=FRAME_START)
            element.keyframe_insert(data_path="radius", frame=FRAME_START)
            element.keyframe_insert(data_path="co", frame=spawn - 1)
            element.keyframe_insert(data_path="radius", frame=spawn - 1)

        element.radius = item["radius"]
        for frame in range(spawn, FRAME_END + 1):
            element.co = item["positions"][frame]
            element.keyframe_insert(data_path="co", frame=frame)
        element.keyframe_insert(data_path="radius", frame=spawn)

    if meta.animation_data and meta.animation_data.action:
        for fcurve in meta.animation_data.action.fcurves:
            for point in fcurve.keyframe_points:
                point.interpolation = "LINEAR"

    return obj, meta


def close_pairs_at_frame(trajectories, frame: int) -> tuple[int, int]:
    active = []
    for item in trajectories:
        if frame >= item["spawn"]:
            active.append((Vector(item["positions"][frame]), item["radius"]))

    close_pairs = 0
    for i in range(len(active)):
        pi, ri = active[i]
        for j in range(i + 1, len(active)):
            pj, rj = active[j]
            if (pi - pj).length < (ri + rj) * 1.55:
                close_pairs += 1
    return len(active), close_pairs


def make_stage():
    basin_mat = make_material("Basin", (0.035, 0.045, 0.055), roughness=0.24, metallic=0.72)
    floor_mat = make_material("Floor", (0.014, 0.017, 0.022), roughness=0.78, metallic=0.08)

    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=3.6, depth=0.24, location=(0.0, 0.0, 0.20))
    basin = bpy.context.object
    basin.name = "Basin"
    basin.data.materials.append(basin_mat)
    bevel = basin.modifiers.new(name="BasinBevel", type="BEVEL")
    bevel.width = 0.14
    bevel.segments = 4

    bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=3.30, depth=0.10, location=(0.0, 0.0, 0.37))
    inset = bpy.context.object
    inset.name = "BasinInset"
    inset.data.materials.append(floor_mat)

    bpy.ops.mesh.primitive_plane_add(size=20.0, location=(0.0, 0.0, 0.0))
    floor = bpy.context.object
    floor.name = "Ground"
    floor.data.materials.append(floor_mat)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.18, location=(0.0, 0.0, 0.86))
    nozzle = bpy.context.object
    nozzle.name = "Nozzle"
    nozzle.scale = (0.55, 0.55, 1.45)
    nozzle.data.materials.append(basin_mat)


def setup_camera_and_lights(scene):
    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera

    shots = [
        (1, (7.5, -10.0, 5.9), (0.0, 0.0, 1.55), 52.0),
        (72, (7.1, -9.2, 5.4), (0.0, 0.0, 1.35), 55.0),
        (108, (6.5, -8.3, 4.8), (0.0, 0.0, 1.05), 57.0),
        (144, (7.2, -9.0, 5.2), (0.0, 0.0, 0.95), 54.0),
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
        look_at(obj, (0.0, 0.0, 1.1))

    area("Key", (-4.0, -4.5, 7.5), 1050.0, 5.2, (0.70, 0.95, 1.0))
    area("Fill", (4.8, -2.0, 5.4), 620.0, 4.2, (0.34, 0.62, 1.0))
    area("Rim", (1.8, 4.0, 6.5), 920.0, 3.0, (1.0, 0.42, 0.18))


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

    trajectories, max_height, total_bounces = build_trajectories()
    make_stage()
    meta_obj, meta = make_metaball_fountain(trajectories)
    setup_camera_and_lights(scene)

    active_preview, close_pairs = close_pairs_at_frame(trajectories, PREVIEW_FRAME)
    action = meta.animation_data.action if meta.animation_data else None
    fcurve_count = len(action.fcurves) if action else 0
    keyframe_points = sum(len(fc.keyframe_points) for fc in action.fcurves) if action else 0

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
        },
        "motion": {
            "spawn_window": [1, 72],
            "max_height": round(max_height, 6),
            "total_bounces": total_bounces,
            "preview_frame": PREVIEW_FRAME,
            "active_at_preview": active_preview,
            "close_pairs_at_preview": close_pairs,
        },
        "blend": BLEND_PATH.name,
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    scene.frame_set(FRAME_START)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

    print(f"BLENDER_ENGINE={engine}")
    print(f"METABALL_ELEMENTS={len(meta.elements)}")
    print(f"METABALL_FCURVES={fcurve_count}")
    print(f"METABALL_KEYFRAME_POINTS={keyframe_points}")
    print(f"FOUNTAIN_MAX_HEIGHT={max_height:.6f}")
    print(f"FOUNTAIN_TOTAL_BOUNCES={total_bounces}")
    print(f"FOUNTAIN_PREVIEW_ACTIVE={active_preview}")
    print(f"FOUNTAIN_PREVIEW_CLOSE_PAIRS={close_pairs}")
    print(f"BLEND_PATH={BLEND_PATH}")
    print(f"REPORT_PATH={REPORT_PATH}")


if __name__ == "__main__":
    build_scene()
