from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path.cwd()
OUTPUT = ROOT / "output"
OUTPUT.mkdir(parents=True, exist_ok=True)

CACHE_DIR = OUTPUT / "fluid-cache"
VIDEO_PATH = OUTPUT / "fluid-dam-break.mp4"
POSTER_PATH = OUTPUT / "poster.png"
SIM_BLEND_PATH = OUTPUT / "fluid-sim.blend"
RESULT_BLEND_PATH = OUTPUT / "fluid-result.blend"

FRAME_START = 1
FRAME_END = 42
POSTER_FRAME = 32


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for blocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
    ):
        for block in list(blocks):
            if block.users == 0:
                blocks.remove(block)


def apply_scale(obj) -> None:
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.select_set(False)


def smooth(obj) -> None:
    mesh = getattr(obj, "data", None)
    if mesh is not None and getattr(mesh, "polygons", None):
        for polygon in mesh.polygons:
            polygon.use_smooth = True


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


def principled_material(name, base, metallic=0.0, roughness=0.35, transmission=0.0, ior=1.45):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = metallic
    if "Roughness" in bsdf.inputs:
        bsdf.inputs["Roughness"].default_value = roughness
    if "IOR" in bsdf.inputs:
        bsdf.inputs["IOR"].default_value = ior
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    elif "Transmission" in bsdf.inputs:
        bsdf.inputs["Transmission"].default_value = transmission
    return mat


def new_cube(name, location, dimensions, material=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    apply_scale(obj)
    if material is not None:
        obj.data.materials.append(material)
    return obj


def fluid_settings(modifier, attr_name):
    for _ in range(6):
        bpy.context.view_layer.update()
        value = getattr(modifier, attr_name)
        if value is not None:
            return value
    raise RuntimeError(f"Fluid settings unavailable: {attr_name}")


def add_effector(obj) -> None:
    mod = obj.modifiers.new("FluidEffector", "FLUID")
    mod.fluid_type = "EFFECTOR"
    settings = fluid_settings(mod, "effector_settings")
    if hasattr(settings, "surface_distance"):
        settings.surface_distance = 0.001


def add_area_light(name, location, energy, size, color, target=(0.0, 0.0, 1.0)):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, target)


def select_only(obj) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def setup_scene():
    clear_scene()
    scene = bpy.context.scene
    engine = choose_engine(scene)

    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.render.film_transparent = False

    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.008, 0.015, 0.028, 1.0)
    bg.inputs["Strength"].default_value = 0.22

    water = principled_material(
        "Water",
        (0.025, 0.19, 0.42),
        roughness=0.06,
        transmission=0.72,
        ior=1.333,
    )
    concrete = principled_material("Concrete", (0.17, 0.19, 0.22), roughness=0.55)
    obstacle_mat = principled_material("Obstacle", (0.27, 0.29, 0.32), metallic=0.15, roughness=0.26)

    domain = new_cube("LiquidDomain", (0.0, 0.0, 1.55), (6.4, 3.4, 3.4), water)
    domain_mod = domain.modifiers.new("FluidDomain", "FLUID")
    domain_mod.fluid_type = "DOMAIN"
    select_only(domain)
    domain_settings = fluid_settings(domain_mod, "domain_settings")
    domain_settings.domain_type = "LIQUID"
    domain_settings.cache_type = "MODULAR"
    domain_settings.cache_directory = str(CACHE_DIR)
    domain_settings.cache_frame_start = FRAME_START
    domain_settings.cache_frame_end = FRAME_END
    domain_settings.resolution_max = 32
    domain_settings.time_scale = 1.0
    domain_settings.timesteps_min = 1
    domain_settings.timesteps_max = 4
    domain_settings.use_mesh = True
    domain_settings.mesh_scale = 1
    domain_settings.mesh_generator = "UNION"
    domain_settings.mesh_particle_radius = 1.7
    domain_settings.particle_number = 1
    domain_settings.particle_min = 4
    domain_settings.particle_max = 8
    domain_settings.simulation_method = "FLIP"
    domain_settings.use_fractions = False
    domain_settings.cache_resumable = False

    for border in (
        "use_collision_border_front",
        "use_collision_border_back",
        "use_collision_border_left",
        "use_collision_border_right",
        "use_collision_border_bottom",
    ):
        if hasattr(domain_settings, border):
            setattr(domain_settings, border, True)
    if hasattr(domain_settings, "use_collision_border_top"):
        domain_settings.use_collision_border_top = False

    flow = new_cube("InitialWaterBlock", (-1.85, 0.0, 1.20), (1.65, 2.45, 2.15))
    flow.hide_render = True
    flow_mod = flow.modifiers.new("FluidFlow", "FLUID")
    flow_mod.fluid_type = "FLOW"
    select_only(flow)
    flow_settings = fluid_settings(flow_mod, "flow_settings")
    flow_settings.flow_type = "LIQUID"
    flow_settings.flow_behavior = "GEOMETRY"
    flow_settings.surface_distance = 1.2

    floor = new_cube("Floor", (0.0, 0.0, -0.14), (6.0, 3.0, 0.24), concrete)
    add_effector(floor)

    obstacle = new_cube("CenterBlock", (0.55, 0.0, 0.56), (0.72, 1.35, 1.15), obstacle_mat)
    obstacle.rotation_euler[2] = math.radians(8.0)
    add_effector(obstacle)

    lip = new_cube("LowBarrier", (1.78, 0.0, 0.24), (0.18, 2.35, 0.48), obstacle_mat)
    add_effector(lip)

    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    camera.location = (7.35, -8.9, 4.85)
    camera_data.lens = 50.0
    look_at(camera, (0.15, 0.0, 0.9))

    camera.keyframe_insert(data_path="location", frame=FRAME_START)
    camera.location = (6.8, -8.25, 4.55)
    camera.keyframe_insert(data_path="location", frame=FRAME_END)

    add_area_light("Key", (2.5, -4.0, 7.5), 1200.0, 5.0, (0.76, 0.88, 1.0))
    add_area_light("Rim", (-3.2, 2.8, 5.5), 950.0, 4.0, (0.12, 0.52, 1.0))
    add_area_light("WarmFill", (3.5, 3.0, 3.0), 650.0, 3.0, (1.0, 0.52, 0.28))

    return scene, domain, flow, (floor, obstacle, lip), engine


def bake_fluid(domain) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    select_only(domain)

    print("FLUID_BAKE_DATA_BEGIN")
    result = bpy.ops.fluid.bake_data()
    print(f"FLUID_BAKE_DATA_RESULT={sorted(result)}")
    if "FINISHED" not in result:
        raise RuntimeError(f"Fluid data bake failed: {result}")

    select_only(domain)
    print("FLUID_BAKE_MESH_BEGIN")
    result = bpy.ops.fluid.bake_mesh()
    print(f"FLUID_BAKE_MESH_RESULT={sorted(result)}")
    if "FINISHED" not in result:
        raise RuntimeError(f"Fluid mesh bake failed: {result}")


def make_static_snapshot(scene, domain, hidden_objects) -> None:
    scene.frame_set(POSTER_FRAME)
    bpy.context.view_layer.update()

    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = domain.evaluated_get(depsgraph)
    snapshot_mesh = bpy.data.meshes.new_from_object(
        evaluated,
        preserve_all_data_layers=True,
        depsgraph=depsgraph,
    )
    if len(snapshot_mesh.vertices) < 16:
        raise RuntimeError(f"Frozen fluid mesh unexpectedly small: {len(snapshot_mesh.vertices)} vertices")

    snapshot = bpy.data.objects.new("FrozenFluidSnapshot", snapshot_mesh)
    bpy.context.collection.objects.link(snapshot)
    snapshot.matrix_world = domain.matrix_world.copy()
    smooth(snapshot)

    for obj in (domain, *hidden_objects):
        obj.hide_render = True
        obj.hide_viewport = True

    bpy.ops.wm.save_as_mainfile(filepath=str(RESULT_BLEND_PATH), copy=True)

    snapshot.hide_render = True
    snapshot.hide_viewport = True
    domain.hide_render = False
    domain.hide_viewport = False
    for obj in hidden_objects:
        obj.hide_viewport = False


def render_outputs(scene) -> None:
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.filepath = str(VIDEO_PATH)
    bpy.ops.render.render(animation=True)

    scene.frame_set(POSTER_FRAME)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(POSTER_PATH)
    bpy.ops.render.render(write_still=True)


def main() -> None:
    scene, domain, flow, effectors, engine = setup_scene()

    bpy.ops.wm.save_as_mainfile(filepath=str(SIM_BLEND_PATH))
    bake_fluid(domain)

    scene.frame_set(POSTER_FRAME)
    bpy.ops.wm.save_as_mainfile(filepath=str(SIM_BLEND_PATH))

    render_outputs(scene)
    make_static_snapshot(scene, domain, (flow, *effectors))

    cache_bytes = sum(p.stat().st_size for p in CACHE_DIR.rglob("*") if p.is_file())
    print(f"BLENDER_ENGINE={engine}")
    print(f"FLUID_CACHE_BYTES={cache_bytes}")
    print(f"VIDEO_PATH={VIDEO_PATH}")
    print(f"SIM_BLEND_PATH={SIM_BLEND_PATH}")
    print(f"RESULT_BLEND_PATH={RESULT_BLEND_PATH}")


if __name__ == "__main__":
    main()
