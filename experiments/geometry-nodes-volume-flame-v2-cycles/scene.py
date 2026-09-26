from __future__ import annotations

import json
import math
import os
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path.cwd()
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
BLEND_PATH = OUTPUT_DIR / "geometry-nodes-volume-flame-v2-cycles.blend"
REPORT_PATH = OUTPUT_DIR / "geometry-nodes-volume-flame-v2-cycles-report.json"

FRAME_START, FRAME_END, FPS = 1, 48, 24
RESOLUTION_X, RESOLUTION_Y = 480, 360
RENDER_SAMPLES = 16
PREPARE_ONLY = os.environ.get("BLENDER_PREPARE_ONLY") == "1"


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def choose_engine(scene) -> str:
    scene.render.engine = "CYCLES"
    return "CYCLES"


def configure_cycles(scene) -> int:
    cycles = scene.cycles
    cycles.device = "CPU"
    cycles.samples = 12
    cycles.use_adaptive_sampling = True
    cycles.max_bounces = 4
    cycles.diffuse_bounces = 1
    cycles.glossy_bounces = 1
    cycles.transmission_bounces = 2
    cycles.volume_bounces = 2
    cycles.transparent_max_bounces = 2
    cycles.use_denoising = False
    return int(cycles.samples)


def look_at(obj, point=(0.0, 0.0, 0.0)) -> None:
    direction = Vector(point) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def phyllotaxis(count: int, radius: float):
    verts = []
    golden = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(count):
        t = (i + 0.5) / count
        r = radius * math.sqrt(t)
        a = i * golden
        verts.append((r * math.cos(a), r * math.sin(a), 0.0))
    return verts


def make_seed_object(name: str, count: int, radius: float):
    mesh = bpy.data.meshes.new(f"{name}Mesh")
    mesh.from_pydata(phyllotaxis(count, radius), [], [])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def make_volume_material(name: str, color, density: float, emission: float, blackbody: float, temperature: float):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    vol = nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (*color, 1.0)
    vol.inputs["Emission Color"].default_value = (*color, 1.0)
    vol.inputs["Density"].default_value = density
    vol.inputs["Emission Strength"].default_value = emission
    vol.inputs["Blackbody Intensity"].default_value = blackbody
    vol.inputs["Temperature"].default_value = temperature
    links.new(vol.outputs["Volume"], out.inputs["Volume"])
    return mat


def make_surface_material(name: str, color, metallic: float, roughness: float):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def build_flame_group(host, material, *, name: str, height: float, rise: float, sway: float, scale: float, radius_min: float, radius_max: float, density: float, voxel: float):
    group = bpy.data.node_groups.new(name, "GeometryNodeTree")
    group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n, l = group.nodes, group.links
    gi = n.new("NodeGroupInput")
    go = n.new("NodeGroupOutput")
    pos = n.new("GeometryNodeInputPosition")
    sep = n.new("ShaderNodeSeparateXYZ")
    idx = n.new("GeometryNodeInputIndex")
    time = n.new("GeometryNodeInputSceneTime")
    m2p = n.new("GeometryNodeMeshToPoints")
    m2p.mode = "VERTICES"
    set_pos = n.new("GeometryNodeSetPosition")
    p2v = n.new("GeometryNodePointsToVolume")
    p2v.resolution_mode = "VOXEL_SIZE"
    p2v.inputs["Density"].default_value = density
    p2v.inputs["Voxel Size"].default_value = voxel
    p2v.inputs["Radius"].default_value = radius_max * 1.35
    set_mat = n.new("GeometryNodeSetMaterial")
    set_mat.inputs["Material"].default_value = material

    age_mul = n.new("ShaderNodeMath"); age_mul.operation = "MULTIPLY"; age_mul.inputs[1].default_value = 0.045
    time_mul = n.new("ShaderNodeMath"); time_mul.operation = "MULTIPLY"; time_mul.inputs[1].default_value = rise
    age_add = n.new("ShaderNodeMath"); age_add.operation = "ADD"
    age = n.new("ShaderNodeMath"); age.operation = "FRACT"
    inv_age = n.new("ShaderNodeMath"); inv_age.operation = "SUBTRACT"; inv_age.inputs[0].default_value = 1.0
    rad_span = n.new("ShaderNodeMath"); rad_span.operation = "SUBTRACT"; rad_span.inputs[0].default_value = radius_max; rad_span.inputs[1].default_value = radius_min
    rad_mul = n.new("ShaderNodeMath"); rad_mul.operation = "MULTIPLY"
    rad_add = n.new("ShaderNodeMath"); rad_add.operation = "ADD"; rad_add.inputs[1].default_value = radius_min

    sway_idx = n.new("ShaderNodeMath"); sway_idx.operation = "MULTIPLY"; sway_idx.inputs[1].default_value = 0.41
    sway_time = n.new("ShaderNodeMath"); sway_time.operation = "MULTIPLY"; sway_time.inputs[1].default_value = sway
    sway_phase = n.new("ShaderNodeMath"); sway_phase.operation = "ADD"
    sway_x_wave = n.new("ShaderNodeMath"); sway_x_wave.operation = "SINE"
    sway_y_phase = n.new("ShaderNodeMath"); sway_y_phase.operation = "ADD"; sway_y_phase.inputs[1].default_value = 1.5707963
    sway_y_wave = n.new("ShaderNodeMath"); sway_y_wave.operation = "SINE"
    sway_amp = n.new("ShaderNodeMath"); sway_amp.operation = "MULTIPLY"; sway_amp.inputs[1].default_value = scale
    sway_x = n.new("ShaderNodeMath"); sway_x.operation = "MULTIPLY"
    sway_y = n.new("ShaderNodeMath"); sway_y.operation = "MULTIPLY"
    pull_x = n.new("ShaderNodeMath"); pull_x.operation = "MULTIPLY"
    pull_y = n.new("ShaderNodeMath"); pull_y.operation = "MULTIPLY"
    pull_x_n = n.new("ShaderNodeMath"); pull_x_n.operation = "MULTIPLY"; pull_x_n.inputs[1].default_value = -1.1
    pull_y_n = n.new("ShaderNodeMath"); pull_y_n.operation = "MULTIPLY"; pull_y_n.inputs[1].default_value = -1.1
    x_add = n.new("ShaderNodeMath"); x_add.operation = "ADD"
    y_add = n.new("ShaderNodeMath"); y_add.operation = "ADD"
    z_mul = n.new("ShaderNodeMath"); z_mul.operation = "MULTIPLY"; z_mul.inputs[1].default_value = height
    combine = n.new("ShaderNodeCombineXYZ")

    l.new(gi.outputs["Geometry"], m2p.inputs["Mesh"])
    l.new(pos.outputs["Position"], sep.inputs["Vector"])
    l.new(idx.outputs["Index"], age_mul.inputs[0])
    l.new(time.outputs["Seconds"], time_mul.inputs[0])
    l.new(age_mul.outputs["Value"], age_add.inputs[0])
    l.new(time_mul.outputs["Value"], age_add.inputs[1])
    l.new(age_add.outputs["Value"], age.inputs[0])
    l.new(age.outputs["Value"], inv_age.inputs[1])
    l.new(inv_age.outputs["Value"], rad_mul.inputs[0])
    l.new(rad_span.outputs["Value"], rad_mul.inputs[1])
    l.new(rad_mul.outputs["Value"], rad_add.inputs[0])
    l.new(rad_add.outputs["Value"], m2p.inputs["Radius"])
    l.new(m2p.outputs["Points"], set_pos.inputs["Geometry"])

    l.new(idx.outputs["Index"], sway_idx.inputs[0])
    l.new(time.outputs["Seconds"], sway_time.inputs[0])
    l.new(sway_idx.outputs["Value"], sway_phase.inputs[0])
    l.new(sway_time.outputs["Value"], sway_phase.inputs[1])
    l.new(sway_phase.outputs["Value"], sway_x_wave.inputs[0])
    l.new(sway_phase.outputs["Value"], sway_y_phase.inputs[0])
    l.new(sway_y_phase.outputs["Value"], sway_y_wave.inputs[0])
    l.new(age.outputs["Value"], sway_amp.inputs[0])
    l.new(sway_x_wave.outputs["Value"], sway_x.inputs[0])
    l.new(sway_amp.outputs["Value"], sway_x.inputs[1])
    l.new(sway_y_wave.outputs["Value"], sway_y.inputs[0])
    l.new(sway_amp.outputs["Value"], sway_y.inputs[1])

    l.new(sep.outputs["X"], pull_x.inputs[0]); l.new(age.outputs["Value"], pull_x.inputs[1]); l.new(pull_x.outputs["Value"], pull_x_n.inputs[0])
    l.new(sep.outputs["Y"], pull_y.inputs[0]); l.new(age.outputs["Value"], pull_y.inputs[1]); l.new(pull_y.outputs["Value"], pull_y_n.inputs[0])
    l.new(pull_x_n.outputs["Value"], x_add.inputs[0]); l.new(sway_x.outputs["Value"], x_add.inputs[1])
    l.new(pull_y_n.outputs["Value"], y_add.inputs[0]); l.new(sway_y.outputs["Value"], y_add.inputs[1])
    l.new(age.outputs["Value"], z_mul.inputs[0])
    l.new(x_add.outputs["Value"], combine.inputs["X"])
    l.new(y_add.outputs["Value"], combine.inputs["Y"])
    l.new(z_mul.outputs["Value"], combine.inputs["Z"])
    l.new(combine.outputs["Vector"], set_pos.inputs["Offset"])
    l.new(set_pos.outputs["Geometry"], p2v.inputs["Points"])
    l.new(p2v.outputs["Volume"], set_mat.inputs["Geometry"])
    l.new(set_mat.outputs["Geometry"], go.inputs["Geometry"])

    mod = host.modifiers.new(name="GeometryNodes", type="NODES")
    mod.node_group = group
    return group


def collect_material_snapshot(material):
    node = material.node_tree.nodes.get("Principled Volume")
    return {
        "name": material.name,
        "density": node.inputs["Density"].default_value,
        "emission_strength": node.inputs["Emission Strength"].default_value,
        "blackbody_intensity": node.inputs["Blackbody Intensity"].default_value,
        "temperature": node.inputs["Temperature"].default_value,
    }


def build_scene() -> None:
    clear_scene()
    scene = bpy.context.scene
    engine = choose_engine(scene)
    render_samples = configure_cycles(scene)
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.fps = FPS
    scene.render.resolution_x = RESOLUTION_X
    scene.render.resolution_y = RESOLUTION_Y
    scene.render.film_transparent = False
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.0045, 0.0045, 0.0068, 1.0)
    bg.inputs["Strength"].default_value = 0.035

    floor_mat = make_surface_material("Floor", (0.015, 0.015, 0.02), 0.06, 0.92)
    burner_mat = make_surface_material("Burner", (0.03, 0.032, 0.038), 0.35, 0.48)
    outer_mat = make_volume_material("OuterFlameMaterial", (1.0, 0.36, 0.08), 0.22, 1.10, 0.28, 1425.0)
    core_mat = make_volume_material("CoreFlameMaterial", (1.0, 0.88, 0.55), 0.10, 1.55, 0.46, 1980.0)

    outer = make_seed_object("OuterFlameHost", 520, 0.44)
    core = make_seed_object("CoreFlameHost", 180, 0.14)
    outer_group = build_flame_group(outer, outer_mat, name="GN_OuterVolumeFlameV2Cycles", height=2.65, rise=0.54, sway=2.35, scale=0.23, radius_min=0.018, radius_max=0.070, density=0.62, voxel=0.070)
    core_group = build_flame_group(core, core_mat, name="GN_CoreVolumeFlameV2Cycles", height=1.85, rise=0.66, sway=2.70, scale=0.08, radius_min=0.010, radius_max=0.040, density=0.78, voxel=0.048)

    bpy.ops.mesh.primitive_plane_add(size=12.0, location=(0.0, 0.0, -0.05))
    floor = bpy.context.object; floor.name = "Floor"; floor.data.materials.append(floor_mat)
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.28, depth=0.32, location=(0.0, 0.0, 0.11))
    burner = bpy.context.object; burner.name = "Burner"; burner.data.materials.append(burner_mat)
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.12, depth=0.14, location=(0.0, 0.0, 0.34))
    nozzle = bpy.context.object; nozzle.name = "Nozzle"; nozzle.data.materials.append(burner_mat)

    cam_data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", cam_data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    cam.location = (3.6, -5.5, 2.45)
    cam_data.lens = 62.0
    look_at(cam, (0.0, 0.0, 1.15))

    for name, location, energy, size, color in [
        ("Fill", (-3.0, -2.0, 2.5), 90.0, 4.5, (0.32, 0.36, 0.58)),
        ("Rim", (1.7, 2.7, 2.1), 55.0, 2.6, (0.95, 0.45, 0.18)),
    ]:
        light = bpy.data.lights.new(name=name, type="AREA")
        light.energy = energy; light.shape = "DISK"; light.size = size; light.color = color
        obj = bpy.data.objects.new(name, light); bpy.context.collection.objects.link(obj); obj.location = location; look_at(obj, (0.0, 0.0, 1.3))
    point = bpy.data.lights.new(name="GroundGlow", type="POINT")
    point.energy = 18.0; point.color = (1.0, 0.43, 0.12)
    point_obj = bpy.data.objects.new("GroundGlow", point); bpy.context.collection.objects.link(point_obj); point_obj.location = (0.0, 0.0, 0.65)

    report = {
        "render_mode": "frame-sequence",
        "engine": engine,
        "frame_start": FRAME_START,
        "frame_end": FRAME_END,
        "fps": FPS,
        "resolution_x": RESOLUTION_X,
        "resolution_y": RESOLUTION_Y,
        "requested_render_samples": RENDER_SAMPLES,
        "effective_render_samples": render_samples,
        "prepared_only": PREPARE_ONLY,
        "materials": {"outer": collect_material_snapshot(outer_mat), "core": collect_material_snapshot(core_mat)},
        "groups": [
            {"host": outer.name, "group": outer_group.name, "node_count": len(outer_group.nodes), "node_types": [n.bl_idname for n in outer_group.nodes], "seed_point_count": 520, "seed_radius": 0.44},
            {"host": core.name, "group": core_group.name, "node_count": len(core_group.nodes), "node_types": [n.bl_idname for n in core_group.nodes], "seed_point_count": 180, "seed_radius": 0.14},
        ],
        "blend": BLEND_PATH.name,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

    print(f"BLENDER_ENGINE={engine}")
    print(f"RENDER_RESOLUTION={RESOLUTION_X}x{RESOLUTION_Y}")
    print(f"RENDER_SAMPLES={render_samples if render_samples is not None else 'default'}")
    print(f"BLEND_PATH={BLEND_PATH}")
    print(f"REPORT_PATH={REPORT_PATH}")
    if PREPARE_ONLY:
        print("BLENDER_PREPARE_ONLY=1")


if __name__ == "__main__":
    build_scene()
