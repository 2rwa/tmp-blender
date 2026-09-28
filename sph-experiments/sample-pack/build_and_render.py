from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from pxr import Gf, Usd, UsdGeom, Vt


ROOT = Path.cwd()
POINT_RADIUS = 0.065
CASE_COLORS = {
    "dam-break": (0.03, 0.30, 0.95),
    "tall-column": (0.05, 0.62, 1.00),
    "falling-slug": (0.08, 0.82, 0.72),
    "two-towers": (0.40, 0.50, 1.00),
    "tilted-surge": (0.20, 0.72, 0.95),
}


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


def make_material(name: str, base: tuple[float, float, float], roughness: float = 0.28):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    bsdf.inputs["Metallic"].default_value = 0.05
    bsdf.inputs["Roughness"].default_value = roughness
    emission = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
    if emission is not None:
        emission.default_value = (*base, 1.0)
    strength = bsdf.inputs.get("Emission Strength")
    if strength is not None:
        strength.default_value = 0.08
    return mat


def find_socket(collection, name: str):
    sock = collection.get(name)
    if sock is None:
        raise RuntimeError(f"socket {name!r} not found; have {[s.name for s in collection]}")
    return sock


def create_point_prototype(mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=1,
        radius=POINT_RADIUS,
        location=(0.0, 0.0, -10.0),
    )
    obj = bpy.context.object
    obj.name = "SPHPointPrototype"
    obj.data.materials.append(mat)
    obj.hide_render = True
    obj.display_type = "WIRE"
    return obj


def make_geometry_nodes(obj: bpy.types.Object, prototype: bpy.types.Object):
    group = bpy.data.node_groups.new("SPH Lightweight Points", "GeometryNodeTree")
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

    modifier = obj.modifiers.new("SPH Points via Geometry Nodes", "NODES")
    modifier.node_group = group
    return modifier, group


def author_usd(cache: Path, manifest: dict, usd_path: Path) -> float:
    stage = Usd.Stage.CreateNew(str(usd_path))
    stage.SetStartTimeCode(1)
    stage.SetEndTimeCode(manifest["frames"])
    stage.SetFramesPerSecond(manifest["fps"])
    stage.SetTimeCodesPerSecond(manifest["fps"])
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

    particles = UsdGeom.Mesh.Define(stage, "/SPHPoints")
    particles.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
    particles.CreateFaceVertexCountsAttr().Set(Vt.IntArray([]))
    particles.CreateFaceVertexIndicesAttr().Set(Vt.IntArray([]))
    points_attr = particles.CreatePointsAttr()

    started = time.perf_counter()
    for record in manifest["frames_data"]:
        frame = int(record["sequence_frame"])
        data = np.load(cache / record["file"])
        points_attr.Set(vec3_array(to_blender(data["points"])), Usd.TimeCode(frame))
    stage.GetRootLayer().Save()
    return time.perf_counter() - started


def main() -> None:
    args = parse_args()
    cache = args.cache.resolve()
    manifest = json.loads((cache / "manifest.json").read_text(encoding="utf-8"))
    if manifest["case"] != args.case:
        raise RuntimeError(f"cache case mismatch: {manifest['case']} != {args.case}")

    base = ROOT / "output" / f"sph-sample-{args.case}"
    base.mkdir(parents=True, exist_ok=True)
    usd_path = base / "sph-points.usdc"
    blend_path = base / f"sph-sample-{args.case}.blend"
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

    point_obj = bpy.data.objects.get("SPHPoints")
    if point_obj is None:
        raise RuntimeError(f"SPHPoints missing: {[o.name for o in scene.objects]}")

    point_mat = make_material("SPHWater", CASE_COLORS.get(args.case, (0.04, 0.35, 0.95)))
    floor_mat = make_material("Floor", (0.025, 0.035, 0.05), roughness=0.60)
    prototype = create_point_prototype(point_mat)
    _, node_group = make_geometry_nodes(point_obj, prototype)

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
        look_at(light, (0.0, 0.0, 0.75))

    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    camera.location = (4.8, -7.3, 3.5)
    camera_data.lens = 50.0
    look_at(camera, (0.0, 0.0, 0.78))

    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            pass

    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100

    nodes = {node.bl_idname for node in node_group.nodes}
    required_nodes = {
        "GeometryNodeMeshToPoints",
        "GeometryNodeObjectInfo",
        "GeometryNodeInstanceOnPoints",
        "GeometryNodeRealizeInstances",
    }
    missing_nodes = sorted(required_nodes - nodes)
    if missing_nodes:
        raise RuntimeError(f"missing Geometry Nodes: {missing_nodes}")

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
    errors = []
    check_t0 = time.perf_counter()
    for frame in check_frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph.update()
        evaluated = point_obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            vertices = len(mesh.vertices)
            faces = len(mesh.polygons)
        finally:
            evaluated.to_mesh_clear()
        if vertices <= int(manifest["particle_count"]):
            errors.append(f"frame {frame}: GN output too small: {vertices} vertices")
        if faces <= 0:
            errors.append(f"frame {frame}: GN output has no faces")
        checks.append({"frame": frame, "vertices": vertices, "faces": faces})
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
        cache_file.filepath = "//sph-points.usdc"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    validation = {
        "case": args.case,
        "representation": "animated-point-usd-plus-geometry-nodes-instancing",
        "frames": frame_count,
        "fps": manifest["fps"],
        "particle_count": manifest["particle_count"],
        "velocity_stats": manifest["velocity_stats"],
        "first_aabb": {
            "min": manifest["frames_data"][0]["aabb_min"],
            "max": manifest["frames_data"][0]["aabb_max"],
        },
        "last_aabb": {
            "min": manifest["frames_data"][-1]["aabb_min"],
            "max": manifest["frames_data"][-1]["aabb_max"],
        },
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
            "nodes": sorted(nodes),
            "modifier_stack": [m.type for m in point_obj.modifiers],
        },
        "checks": checks,
        "errors": errors,
    }
    validation_path.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    main()
