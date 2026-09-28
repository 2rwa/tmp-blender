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
ARROW_SCALE = 0.32
ARROW_MIN_LENGTH = 0.035
POINT_RADIUS = 0.038
ACCEL_BIN_EDGES = (0.2, 0.4, 0.6, 0.8)
ACCEL_COLORS = (
    (0.03, 0.20, 0.95),
    (0.00, 0.70, 1.00),
    (0.15, 0.95, 0.55),
    (1.00, 0.78, 0.04),
    (1.00, 0.12, 0.02),
)


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("velocity", "acceleration", "combined"), required=True)
    parser.add_argument("--cache", type=Path, required=True)
    return parser.parse_args(argv)


def to_blender(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    out = np.empty_like(values, dtype=np.float32)
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


def make_material(
    name: str,
    base: tuple[float, float, float],
    *,
    metallic: float = 0.0,
    roughness: float = 0.25,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    if emission_strength > 0.0:
        emission = bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission")
        if emission is not None:
            emission.default_value = (*base, 1.0)
        strength = bsdf.inputs.get("Emission Strength")
        if strength is not None:
            strength.default_value = emission_strength
    return mat


def find_socket(collection, name: str):
    sock = collection.get(name)
    if sock is None:
        raise RuntimeError(f"socket {name!r} not found; have {[s.name for s in collection]}")
    return sock


def find_any_socket(collection, *names: str):
    for name in names:
        sock = collection.get(name)
        if sock is not None:
            return sock
    raise RuntimeError(f"none of sockets {names!r} found; have {[s.name for s in collection]}")


def object_info(nodes, obj: bpy.types.Object, location: tuple[float, float]):
    node = nodes.new("GeometryNodeObjectInfo")
    node.location = location
    find_socket(node.inputs, "Object").default_value = obj
    return node


def sample_position(nodes, links, geometry_socket, index_socket, location: tuple[float, float]):
    position = nodes.new("GeometryNodeInputPosition")
    position.location = (location[0] - 220, location[1] - 120)
    sample = nodes.new("GeometryNodeSampleIndex")
    sample.location = location
    sample.data_type = "FLOAT_VECTOR"
    sample.domain = "POINT"
    links.new(geometry_socket, find_socket(sample.inputs, "Geometry"))
    links.new(find_socket(position.outputs, "Position"), find_socket(sample.inputs, "Value"))
    links.new(index_socket, find_socket(sample.inputs, "Index"))
    return find_socket(sample.outputs, "Value"), sample, position


def create_arrow_prototype(mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cone_add(
        vertices=8,
        radius1=0.026,
        radius2=0.0,
        depth=1.0,
        end_fill_type="NGON",
        location=(0.0, 0.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = "VelocityArrowPrototype"
    for vertex in obj.data.vertices:
        vertex.co.z += 0.5
    obj.data.materials.append(mat)
    obj.hide_render = True
    obj.display_type = "WIRE"
    return obj


def create_sphere_prototype(name: str, mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_ico_sphere_add(
        subdivisions=1,
        radius=POINT_RADIUS,
        location=(0.0, 0.0, 0.0),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    obj.hide_render = True
    obj.display_type = "WIRE"
    return obj


def add_acceleration_branch(
    nodes,
    links,
    points_socket,
    accel_value_socket,
    prototype: bpy.types.Object,
    lower: float | None,
    upper: float | None,
    y: float,
):
    proto_info = object_info(nodes, prototype, (80, y - 80))
    instance = nodes.new("GeometryNodeInstanceOnPoints")
    instance.location = (430, y)
    links.new(points_socket, find_socket(instance.inputs, "Points"))
    links.new(find_socket(proto_info.outputs, "Geometry"), find_socket(instance.inputs, "Instance"))

    selections = []
    if lower is not None:
        ge = nodes.new("FunctionNodeCompare")
        ge.location = (-120, y + 20)
        ge.data_type = "FLOAT"
        ge.operation = "GREATER_EQUAL"
        links.new(accel_value_socket, find_socket(ge.inputs, "A"))
        find_socket(ge.inputs, "B").default_value = lower
        selections.append(find_socket(ge.outputs, "Result"))
    if upper is not None:
        lt = nodes.new("FunctionNodeCompare")
        lt.location = (-120, y - 90)
        lt.data_type = "FLOAT"
        lt.operation = "LESS_THAN"
        links.new(accel_value_socket, find_socket(lt.inputs, "A"))
        find_socket(lt.inputs, "B").default_value = upper
        selections.append(find_socket(lt.outputs, "Result"))

    if len(selections) == 2:
        both = nodes.new("FunctionNodeBooleanMath")
        both.location = (120, y + 20)
        both.operation = "AND"
        links.new(selections[0], both.inputs[0])
        links.new(selections[1], both.inputs[1])
        selection = find_socket(both.outputs, "Boolean")
    elif len(selections) == 1:
        selection = selections[0]
    else:
        selection = None

    if selection is not None:
        links.new(selection, find_socket(instance.inputs, "Selection"))
    return find_socket(instance.outputs, "Instances")


def make_geometry_nodes(
    obj: bpy.types.Object,
    arrow_points_obj: bpy.types.Object,
    velocity_obj: bpy.types.Object,
    acceleration_obj: bpy.types.Object,
    arrow_proto: bpy.types.Object,
    accel_protos: list[bpy.types.Object],
    mode: str,
    speed_p95: float,
):
    group = bpy.data.node_groups.new(f"SPH Diagnostics {mode}", "GeometryNodeTree")
    group.is_modifier = True
    group.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

    nodes = group.nodes
    links = group.links
    gin = nodes.new("NodeGroupInput")
    gin.location = (-1200, 100)
    gout = nodes.new("NodeGroupOutput")
    gout.location = (1050, 120)
    join = nodes.new("GeometryNodeJoinGeometry")
    join.location = (820, 120)

    outputs = []
    main_points = nodes.new("GeometryNodeMeshToPoints")
    main_points.location = (-930, 270)
    main_points.mode = "VERTICES"
    find_socket(main_points.inputs, "Radius").default_value = POINT_RADIUS
    links.new(find_socket(gin.outputs, "Geometry"), find_socket(main_points.inputs, "Mesh"))

    if mode in ("acceleration", "combined"):
        index = nodes.new("GeometryNodeInputIndex")
        index.location = (-950, 40)
        accel_info = object_info(nodes, acceleration_obj, (-930, -130))
        accel_vector, _, _ = sample_position(
            nodes,
            links,
            find_socket(accel_info.outputs, "Geometry"),
            find_socket(index.outputs, "Index"),
            (-620, -60),
        )
        separate = nodes.new("ShaderNodeSeparateXYZ")
        separate.location = (-360, -60)
        links.new(accel_vector, find_socket(separate.inputs, "Vector"))
        accel_value = find_socket(separate.outputs, "X")

        ranges = [
            (None, ACCEL_BIN_EDGES[0]),
            (ACCEL_BIN_EDGES[0], ACCEL_BIN_EDGES[1]),
            (ACCEL_BIN_EDGES[1], ACCEL_BIN_EDGES[2]),
            (ACCEL_BIN_EDGES[2], ACCEL_BIN_EDGES[3]),
            (ACCEL_BIN_EDGES[3], None),
        ]
        for i, (proto, (lower, upper)) in enumerate(zip(accel_protos, ranges)):
            outputs.append(add_acceleration_branch(
                nodes,
                links,
                find_socket(main_points.outputs, "Points"),
                accel_value,
                proto,
                lower,
                upper,
                440 - i * 170,
            ))

    if mode in ("velocity", "combined"):
        arrow_info = object_info(nodes, arrow_points_obj, (-930, -650))
        arrow_mesh_to_points = nodes.new("GeometryNodeMeshToPoints")
        arrow_mesh_to_points.location = (-690, -650)
        arrow_mesh_to_points.mode = "VERTICES"
        links.new(find_socket(arrow_info.outputs, "Geometry"), find_socket(arrow_mesh_to_points.inputs, "Mesh"))

        sparse_index = nodes.new("GeometryNodeInputIndex")
        sparse_index.location = (-690, -850)
        vel_info = object_info(nodes, velocity_obj, (-930, -980))
        velocity, _, _ = sample_position(
            nodes,
            links,
            find_socket(vel_info.outputs, "Geometry"),
            find_socket(sparse_index.outputs, "Index"),
            (-430, -890),
        )

        speed = nodes.new("ShaderNodeVectorMath")
        speed.location = (-180, -800)
        speed.operation = "LENGTH"
        links.new(velocity, find_socket(speed.inputs, "Vector"))

        divide = nodes.new("ShaderNodeMath")
        divide.location = (20, -800)
        divide.operation = "DIVIDE"
        links.new(find_socket(speed.outputs, "Value"), divide.inputs[0])
        divide.inputs[1].default_value = max(float(speed_p95), 1.0e-6)

        cap = nodes.new("ShaderNodeMath")
        cap.location = (190, -800)
        cap.operation = "MINIMUM"
        links.new(divide.outputs[0], cap.inputs[0])
        cap.inputs[1].default_value = 1.0

        mul = nodes.new("ShaderNodeMath")
        mul.location = (360, -800)
        mul.operation = "MULTIPLY"
        links.new(cap.outputs[0], mul.inputs[0])
        mul.inputs[1].default_value = ARROW_SCALE

        add = nodes.new("ShaderNodeMath")
        add.location = (530, -800)
        add.operation = "ADD"
        links.new(mul.outputs[0], add.inputs[0])
        add.inputs[1].default_value = ARROW_MIN_LENGTH

        combine = nodes.new("ShaderNodeCombineXYZ")
        combine.location = (530, -960)
        combine.inputs["X"].default_value = 1.0
        combine.inputs["Y"].default_value = 1.0
        links.new(add.outputs[0], combine.inputs["Z"])

        align = nodes.new("FunctionNodeAlignEulerToVector")
        align.location = (60, -1040)
        align.axis = "Z"
        find_socket(align.inputs, "Factor").default_value = 1.0
        links.new(velocity, find_socket(align.inputs, "Vector"))

        proto_info = object_info(nodes, arrow_proto, (180, -1170))
        instance = nodes.new("GeometryNodeInstanceOnPoints")
        instance.location = (390, -1130)
        links.new(find_socket(arrow_mesh_to_points.outputs, "Points"), find_socket(instance.inputs, "Points"))
        links.new(find_socket(proto_info.outputs, "Geometry"), find_socket(instance.inputs, "Instance"))
        links.new(find_socket(align.outputs, "Rotation"), find_socket(instance.inputs, "Rotation"))

        scale = nodes.new("GeometryNodeScaleInstances")
        scale.location = (650, -1100)
        links.new(
            find_socket(instance.outputs, "Instances"),
            find_any_socket(scale.inputs, "Instances", "Geometry"),
        )
        links.new(find_socket(combine.outputs, "Vector"), find_socket(scale.inputs, "Scale"))
        outputs.append(find_any_socket(scale.outputs, "Instances", "Geometry"))

        if mode == "velocity":
            base_mat = make_material("VelocityPoint", (0.04, 0.28, 0.95), roughness=0.32, emission_strength=0.1)
            base_proto = create_sphere_prototype("VelocityPointPrototype", base_mat)
            base_info = object_info(nodes, base_proto, (120, 620))
            base_inst = nodes.new("GeometryNodeInstanceOnPoints")
            base_inst.location = (430, 620)
            links.new(find_socket(main_points.outputs, "Points"), find_socket(base_inst.inputs, "Points"))
            links.new(find_socket(base_info.outputs, "Geometry"), find_socket(base_inst.inputs, "Instance"))
            outputs.append(find_socket(base_inst.outputs, "Instances"))

    for output in outputs:
        links.new(output, find_socket(join.inputs, "Geometry"))
    links.new(find_socket(join.outputs, "Geometry"), find_socket(gout.inputs, "Geometry"))

    modifier = obj.modifiers.new(f"SPH Diagnostics {mode}", "NODES")
    modifier.node_group = group
    return modifier, group


def author_usd(cache: Path, manifest: dict, usd_path: Path) -> float:
    stage = Usd.Stage.CreateNew(str(usd_path))
    stage.SetStartTimeCode(1)
    stage.SetEndTimeCode(manifest["frames"])
    stage.SetFramesPerSecond(manifest["fps"])
    stage.SetTimeCodesPerSecond(manifest["fps"])
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

    def point_mesh(path: str):
        mesh = UsdGeom.Mesh.Define(stage, path)
        mesh.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
        mesh.CreateFaceVertexCountsAttr().Set(Vt.IntArray([]))
        mesh.CreateFaceVertexIndicesAttr().Set(Vt.IntArray([]))
        return mesh.CreatePointsAttr()

    p_points = point_mesh("/SPHPoints")
    a_points = point_mesh("/ArrowPoints")
    v_points = point_mesh("/VelocityValues")
    accel_points = point_mesh("/AccelerationValues")

    cube = UsdGeom.Mesh.Define(stage, "/DynamicCube")
    cube.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
    cube.CreateDoubleSidedAttr().Set(True)
    cube.CreateFaceVertexCountsAttr().Set(Vt.IntArray([3] * len(manifest["cube_faces"])))
    cube.CreateFaceVertexIndicesAttr().Set(
        Vt.IntArray([int(i) for face in manifest["cube_faces"] for i in face])
    )
    c_points = cube.CreatePointsAttr()

    stride = int(manifest["sparse_stride"])
    started = time.perf_counter()
    for record in manifest["frames_data"]:
        frame = int(record["sequence_frame"])
        data = np.load(cache / record["file"])
        points = to_blender(data["points"])
        velocity = to_blender(data["velocity"])
        cube_points = to_blender(data["cube"])
        accel_norm = np.asarray(data["acceleration_normalized"], dtype=np.float32)

        sparse_points = points[::stride]
        sparse_velocity = velocity[::stride]
        accel_carrier = np.zeros_like(points, dtype=np.float32)
        accel_carrier[:, 0] = accel_norm

        p_points.Set(vec3_array(points), Usd.TimeCode(frame))
        a_points.Set(vec3_array(sparse_points), Usd.TimeCode(frame))
        v_points.Set(vec3_array(sparse_velocity), Usd.TimeCode(frame))
        accel_points.Set(vec3_array(accel_carrier), Usd.TimeCode(frame))
        c_points.Set(vec3_array(cube_points), Usd.TimeCode(frame))

    stage.GetRootLayer().Save()
    return time.perf_counter() - started


def main() -> None:
    args = parse_args()
    cache = args.cache.resolve()
    manifest = json.loads((cache / "manifest.json").read_text(encoding="utf-8"))

    base = ROOT / "output" / f"sph-point-diagnostics-{args.mode}"
    base.mkdir(parents=True, exist_ok=True)
    usd_path = base / "sph-diagnostics.usdc"
    blend_path = base / f"sph-point-diagnostics-{args.mode}.blend"
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
    arrow_points_obj = bpy.data.objects.get("ArrowPoints")
    velocity_obj = bpy.data.objects.get("VelocityValues")
    acceleration_obj = bpy.data.objects.get("AccelerationValues")
    cube_obj = bpy.data.objects.get("DynamicCube")
    expected = [point_obj, arrow_points_obj, velocity_obj, acceleration_obj, cube_obj]
    if any(obj is None for obj in expected):
        raise RuntimeError(f"missing imported objects: {[o.name for o in scene.objects]}")

    arrow_mat = make_material("VelocityArrow", (1.0, 0.82, 0.08), metallic=0.05, roughness=0.24, emission_strength=0.2)
    cube_mat = make_material("Cube", (0.95, 0.27, 0.04), metallic=0.12, roughness=0.24)
    floor_mat = make_material("Floor", (0.03, 0.04, 0.06), roughness=0.55)
    accel_mats = [
        make_material(f"AccelerationBin{i}", color, roughness=0.27, emission_strength=0.16)
        for i, color in enumerate(ACCEL_COLORS)
    ]

    cube_obj.data.materials.append(cube_mat)
    arrow_proto = create_arrow_prototype(arrow_mat)
    accel_protos = [
        create_sphere_prototype(f"AccelerationPrototype{i}", mat)
        for i, mat in enumerate(accel_mats)
    ]

    _, node_group = make_geometry_nodes(
        point_obj,
        arrow_points_obj,
        velocity_obj,
        acceleration_obj,
        arrow_proto,
        accel_protos,
        args.mode,
        float(manifest["velocity_stats"]["p95"]),
    )

    bpy.ops.mesh.primitive_plane_add(size=8.0, location=(0.0, 0.0, 0.0))
    floor = bpy.context.object
    floor.name = "Floor"
    floor.data.materials.append(floor_mat)

    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.006, 0.010, 0.022, 1.0)
    bg.inputs["Strength"].default_value = 0.23

    for name, location, energy, size, color in (
        ("Key", (3.8, -4.0, 5.5), 1050.0, 4.0, (1.0, 0.78, 0.60)),
        ("Fill", (-3.4, -1.5, 4.0), 650.0, 3.5, (0.42, 0.64, 1.0)),
        ("Rim", (0.0, 4.4, 5.0), 800.0, 3.0, (0.40, 0.78, 1.0)),
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
    camera.location = (4.8, -7.2, 3.6)
    camera_data.lens = 50.0
    look_at(camera, (0.0, 0.0, 0.75))

    for engine in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            pass
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100

    errors = []
    checks = []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    check_frames = [1, 7, 13, 31, 46, 61]
    check_t0 = time.perf_counter()
    for frame in check_frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph.update()

        evaluated = point_obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            out_vertices = len(mesh.vertices)
            out_faces = len(mesh.polygons)
        finally:
            evaluated.to_mesh_clear()

        arrow_eval = arrow_points_obj.evaluated_get(depsgraph)
        arrow_mesh = arrow_eval.to_mesh()
        try:
            arrow_vertices = len(arrow_mesh.vertices)
        finally:
            arrow_eval.to_mesh_clear()

        if out_vertices <= 0 or out_faces <= 0:
            errors.append(f"frame {frame}: empty diagnostic geometry {out_vertices}/{out_faces}")
        if arrow_vertices != int(manifest["sparse_particle_count"]):
            errors.append(
                f"frame {frame}: sparse arrow source {arrow_vertices} != {manifest['sparse_particle_count']}"
            )
        checks.append({
            "frame": frame,
            "diagnostic_vertices": out_vertices,
            "diagnostic_faces": out_faces,
            "arrow_source_vertices": arrow_vertices,
        })
    check_seconds = time.perf_counter() - check_t0

    actual_nodes = {node.bl_idname for node in node_group.nodes}
    required = {"GeometryNodeMeshToPoints", "GeometryNodeInstanceOnPoints", "GeometryNodeJoinGeometry"}
    if args.mode in ("velocity", "combined"):
        required |= {
            "GeometryNodeSampleIndex",
            "FunctionNodeAlignEulerToVector",
            "GeometryNodeScaleInstances",
        }
    if args.mode in ("acceleration", "combined"):
        required |= {"GeometryNodeSampleIndex", "FunctionNodeCompare"}
    missing = sorted(required - actual_nodes)
    if missing:
        errors.append(f"missing GN nodes: {missing}")
    if errors:
        raise RuntimeError("; ".join(errors))

    preview_frame = 31
    preview_data = np.load(cache / manifest["frames_data"][preview_frame - 1]["file"])
    preview_accel = np.asarray(preview_data["acceleration_normalized"], dtype=np.float32)
    hist, _ = np.histogram(preview_accel, bins=(0.0, *ACCEL_BIN_EDGES, 1.000001))

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
        cache_file.filepath = "//sph-diagnostics.usdc"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    validation = {
        "mode": args.mode,
        "representation": "animated-point-carriers-plus-geometry-nodes-diagnostics",
        "frames": manifest["frames"],
        "particle_count": manifest["particle_count"],
        "sparse_stride": manifest["sparse_stride"],
        "sparse_particle_count": manifest["sparse_particle_count"],
        "velocity_stats": manifest["velocity_stats"],
        "acceleration_stats": manifest["acceleration_stats"],
        "preview_acceleration_bin_counts": hist.tolist(),
        "usd_bytes": usd_path.stat().st_size,
        "blend_bytes": blend_path.stat().st_size,
        "preview_bytes": preview_path.stat().st_size,
        "video_bytes": video_path.stat().st_size,
        "usd_author_seconds": usd_author_seconds,
        "usd_import_seconds": import_seconds,
        "geometry_nodes_check_seconds": check_seconds,
        "render_seconds": render_seconds,
        "geometry_nodes": {
            "nodes": sorted(actual_nodes),
            "modifier_stack": [m.type for m in point_obj.modifiers],
        },
        "checks": checks,
        "errors": errors,
    }
    validation_path.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    main()
