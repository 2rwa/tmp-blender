from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from pxr import Gf, Usd, UsdGeom, Vt

ROOT = Path.cwd()
PHASES = ("PhaseA", "PhaseB")
PHASE_COLORS = {
    "PhaseA": (0.03, 0.28, 0.98),
    "PhaseB": (1.00, 0.34, 0.04),
}
POINT_RADIUS = 0.062

def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--cache", type=Path, required=True)
    return parser.parse_args(argv)

def to_blender(points: np.ndarray) -> np.ndarray:
    values = np.asarray(points, dtype=np.float32)
    out = np.empty_like(values)
    out[:, 0] = values[:, 0]
    out[:, 1] = -values[:, 2]
    out[:, 2] = values[:, 1]
    return out

def vec3_array(values: np.ndarray) -> Vt.Vec3fArray:
    return Vt.Vec3fArray([
        Gf.Vec3f(float(x), float(y), float(z))
        for x, y, z in np.asarray(values, dtype=np.float32)
    ])

def look_at(obj: bpy.types.Object, point: tuple[float, float, float]) -> None:
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()

def make_material(name: str, base: tuple[float, float, float], roughness: float = 0.25):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.04
    bsdf.inputs["Roughness"].default_value = roughness
    emission = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
    if emission is not None:
        emission.default_value = (*base, 1.0)
    strength = bsdf.inputs.get("Emission Strength")
    if strength is not None:
        strength.default_value = 0.10
    return mat

def find_socket(collection, name: str):
    sock = collection.get(name)
    if sock is None:
        raise RuntimeError(f"socket {name!r} not found; have {[s.name for s in collection]}")
    return sock

def create_point_prototype(name: str, mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=1,
        radius=POINT_RADIUS,
        location=(0.0, 0.0, -10.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    obj.hide_render = True
    obj.display_type = "WIRE"
    return obj

def make_geometry_nodes(obj: bpy.types.Object, prototype: bpy.types.Object, phase: str):
    group = bpy.data.node_groups.new(f"{phase} Lightweight Points", "GeometryNodeTree")
    group.is_modifier = True
    group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nodes = group.nodes
    links = group.links
    gin = nodes.new("NodeGroupInput")
    gin.location = (-600, 0)
    gout = nodes.new("NodeGroupOutput")
    gout.location = (520, 0)
    mesh_to_points = nodes.new("GeometryNodeMeshToPoints")
    mesh_to_points.location = (-380, 0)
    mesh_to_points.mode = "VERTICES"
    object_info = nodes.new("GeometryNodeObjectInfo")
    object_info.location = (-360, -220)
    find_socket(object_info.inputs, "Object").default_value = prototype
    instance = nodes.new("GeometryNodeInstanceOnPoints")
    instance.location = (-80, 0)
    realize = nodes.new("GeometryNodeRealizeInstances")
    realize.location = (250, 0)
    links.new(find_socket(gin.outputs, "Geometry"), find_socket(mesh_to_points.inputs, "Mesh"))
    links.new(find_socket(mesh_to_points.outputs, "Points"), find_socket(instance.inputs, "Points"))
    links.new(find_socket(object_info.outputs, "Geometry"), find_socket(instance.inputs, "Instance"))
    links.new(find_socket(instance.outputs, "Instances"), find_socket(realize.inputs, "Geometry"))
    links.new(find_socket(realize.outputs, "Geometry"), find_socket(gout.inputs, "Geometry"))
    modifier = obj.modifiers.new(f"{phase} Points via Geometry Nodes", "NODES")
    modifier.node_group = group
    return group

def author_usd(cache: Path, manifest: dict, usd_path: Path) -> float:
    stage = Usd.Stage.CreateNew(str(usd_path))
    stage.SetStartTimeCode(1)
    stage.SetEndTimeCode(manifest["frames"])
    stage.SetFramesPerSecond(manifest["fps"])
    stage.SetTimeCodesPerSecond(manifest["fps"])
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    attrs = {}
    for phase in PHASES:
        mesh = UsdGeom.Mesh.Define(stage, f"/{phase}")
        mesh.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
        mesh.CreateFaceVertexCountsAttr().Set(Vt.IntArray([]))
        mesh.CreateFaceVertexIndicesAttr().Set(Vt.IntArray([]))
        attrs[phase] = mesh.CreatePointsAttr()
    started = time.perf_counter()
    for phase in PHASES:
        for record in manifest["phases"][phase]["frames_data"]:
            frame = int(record["sequence_frame"])
            data = np.load(cache / record["file"])
            attrs[phase].Set(
                vec3_array(to_blender(np.asarray(data["points"], dtype=np.float32))),
                Usd.TimeCode(frame),
            )
    stage.GetRootLayer().Save()
    return time.perf_counter() - started

def distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))

def main() -> None:
    args = parse_args()
    cache = args.cache.resolve()
    manifest = json.loads((cache / "manifest.json").read_text(encoding="utf-8"))
    if manifest["case"] != args.case:
        raise RuntimeError(f"cache case mismatch: {manifest['case']} != {args.case}")

    base = ROOT / "output" / f"sph-two-phase-{args.case}"
    base.mkdir(parents=True, exist_ok=True)
    usd_path = base / "two-phase-points.usdc"
    blend_path = base / f"sph-two-phase-{args.case}.blend"
    preview_path = base / "preview.png"
    video_path = base / "media.mp4"
    validation_path = base / "validation.json"
    usd_author_seconds = author_usd(cache, manifest, usd_path)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    import_t0 = time.perf_counter()
    result = bpy.ops.wm.usd_import(
        filepath=str(usd_path),
        set_frame_range=False,
        import_cameras=False,
        import_curves=False,
        import_lights=False,
        import_materials=False,
        import_meshes=True,
        import_volumes=False,
    )
    import_seconds = time.perf_counter() - import_t0
    if "FINISHED" not in result:
        raise RuntimeError(f"USD import failed: {result}")

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = int(manifest["frames"])
    scene.render.fps = int(manifest["fps"])

    phase_objects = {}
    node_groups = {}
    for phase in PHASES:
        obj = bpy.data.objects.get(phase)
        if obj is None:
            raise RuntimeError(f"missing imported phase {phase}: {[o.name for o in scene.objects]}")
        phase_objects[phase] = obj
        mat = make_material(f"{phase}Material", PHASE_COLORS[phase])
        prototype = create_point_prototype(f"{phase}Prototype", mat)
        node_groups[phase] = make_geometry_nodes(obj, prototype, phase)

    floor_mat = make_material("Floor", (0.025, 0.035, 0.05), roughness=0.60)
    bpy.ops.mesh.primitive_plane_add(size=8.0, location=(0.0, 0.0, 0.0))
    floor = bpy.context.object
    floor.name = "Floor"
    floor.data.materials.append(floor_mat)

    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.006, 0.010, 0.022, 1.0)
    background.inputs["Strength"].default_value = 0.24

    for name, location, energy, size, color in (
        ("Key", (3.8, -4.0, 5.5), 950.0, 4.0, (1.0, 0.80, 0.64)),
        ("Fill", (-3.4, -1.5, 4.0), 600.0, 3.5, (0.44, 0.66, 1.0)),
        ("Rim", (0.0, 4.2, 5.0), 750.0, 3.0, (0.42, 0.80, 1.0)),
    ):
        light_data = bpy.data.lights.new(name=name, type="AREA")
        light_data.energy = energy
        light_data.shape = "DISK"
        light_data.size = size
        light_data.color = color
        light = bpy.data.objects.new(name, light_data)
        bpy.context.collection.objects.link(light)
        light.location = location
        look_at(light, (0.0, 0.0, 0.82))

    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    camera.location = (4.9, -7.4, 3.55)
    camera_data.lens = 50.0
    look_at(camera, (0.0, 0.0, 0.82))

    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            pass
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100

    required_nodes = {
        "GeometryNodeMeshToPoints",
        "GeometryNodeObjectInfo",
        "GeometryNodeInstanceOnPoints",
        "GeometryNodeRealizeInstances",
    }
    errors = []
    group_nodes = {}
    for phase, group in node_groups.items():
        nodes = {node.bl_idname for node in group.nodes}
        group_nodes[phase] = sorted(nodes)
        missing = sorted(required_nodes - nodes)
        if missing:
            errors.append(f"{phase}: missing Geometry Nodes {missing}")

    frame_count = int(manifest["frames"])
    check_frames = sorted(set([
        1,
        max(1, frame_count // 4),
        max(1, frame_count // 2),
        max(1, (frame_count * 3) // 4),
        frame_count,
    ]))
    depsgraph = bpy.context.evaluated_depsgraph_get()
    checks = []
    check_t0 = time.perf_counter()
    for frame in check_frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph.update()
        record = {"frame": frame}
        for phase in PHASES:
            obj = phase_objects[phase]
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            try:
                vertices = len(mesh.vertices)
                faces = len(mesh.polygons)
            finally:
                evaluated.to_mesh_clear()
            expected_particles = int(manifest["phases"][phase]["particle_count"])
            if vertices <= expected_particles:
                errors.append(
                    f"frame {frame} {phase}: GN output too small: {vertices} <= {expected_particles}"
                )
            if faces <= 0:
                errors.append(f"frame {frame} {phase}: GN output has no faces")
            record[phase] = {"vertices": vertices, "faces": faces}
        checks.append(record)
    check_seconds = time.perf_counter() - check_t0
    if errors:
        raise RuntimeError("; ".join(errors))

    preview_frame = max(1, frame_count // 2)
    scene.frame_set(preview_frame)
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(preview_path)
    bpy.ops.render.render(write_still=True)

    scene.frame_set(1)
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.filepath = str(video_path)
    render_t0 = time.perf_counter()
    bpy.ops.render.render(animation=True)
    render_seconds = time.perf_counter() - render_t0

    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    for cache_file in bpy.data.cache_files:
        cache_file.filepath = "//two-phase-points.usdc"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    phase_summary = {}
    for phase in PHASES:
        data = manifest["phases"][phase]
        first = data["frames_data"][0]
        last = data["frames_data"][-1]
        phase_summary[phase] = {
            "particle_count": data["particle_count"],
            "velocity_stats": data["velocity_stats"],
            "first_centroid": first["centroid"],
            "last_centroid": last["centroid"],
            "centroid_displacement": distance(first["centroid"], last["centroid"]),
            "first_aabb": {"min": first["aabb_min"], "max": first["aabb_max"]},
            "last_aabb": {"min": last["aabb_min"], "max": last["aabb_max"]},
        }

    validation = {
        "case": args.case,
        "representation": "two-fluid-models-to-animated-usd-plus-geometry-nodes",
        "frames": frame_count,
        "fps": manifest["fps"],
        "total_particle_count": manifest["total_particle_count"],
        "phases": phase_summary,
        "point_npz_total_bytes": manifest["point_npz_total_bytes"],
        "point_usd_bytes": usd_path.stat().st_size,
        "blend_bytes": blend_path.stat().st_size,
        "preview_bytes": preview_path.stat().st_size,
        "video_bytes": video_path.stat().st_size,
        "usd_author_seconds": usd_author_seconds,
        "usd_import_seconds": import_seconds,
        "geometry_nodes_check_seconds": check_seconds,
        "render_seconds": render_seconds,
        "geometry_nodes": {
            "point_radius": POINT_RADIUS,
            "nodes": group_nodes,
            "modifier_stack": {
                phase: [m.type for m in phase_objects[phase].modifiers]
                for phase in PHASES
            },
        },
        "checks": checks,
        "errors": errors,
    }
    validation_path.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2))

if __name__ == "__main__":
    main()
