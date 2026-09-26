from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path.cwd()
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RENDER_PATH = OUTPUT_DIR / "render.png"
BLEND_PATH = OUTPUT_DIR / "geometry-nodes.blend"
REPORT_PATH = OUTPUT_DIR / "geometry-nodes-report.json"

GRID_VERTICES_X = 31
GRID_VERTICES_Y = 31
GRID_SIZE = 12.0


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.node_groups,
    ):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def make_material(name: str, base_color, metallic: float, roughness: float):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


def look_at(obj, point=(0.0, 0.0, 0.0)) -> None:
    direction = Vector(point) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_area_light(name: str, location, energy: float, size: float, color) -> None:
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, (0.0, 0.0, 0.0))


def choose_engine(scene) -> str:
    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = candidate
            return candidate
        except TypeError:
            continue
    scene.render.engine = "BLENDER_WORKBENCH"
    return "BLENDER_WORKBENCH"


def build_geometry_nodes(host, material) -> bpy.types.NodeTree:
    group = bpy.data.node_groups.new("GN_RippleGrid", "GeometryNodeTree")
    group.interface.new_socket(
        name="Geometry",
        in_out="INPUT",
        socket_type="NodeSocketGeometry",
    )
    group.interface.new_socket(
        name="Geometry",
        in_out="OUTPUT",
        socket_type="NodeSocketGeometry",
    )

    nodes = group.nodes
    links = group.links

    group_input = nodes.new("NodeGroupInput")
    group_input.label = "Unused host geometry"
    group_input.location = (-900, 360)

    grid = nodes.new("GeometryNodeMeshGrid")
    grid.label = "31 x 31 procedural grid"
    grid.location = (-900, 100)
    grid.inputs["Size X"].default_value = GRID_SIZE
    grid.inputs["Size Y"].default_value = GRID_SIZE
    grid.inputs["Vertices X"].default_value = GRID_VERTICES_X
    grid.inputs["Vertices Y"].default_value = GRID_VERTICES_Y

    position = nodes.new("GeometryNodeInputPosition")
    position.location = (-900, -220)

    radius = nodes.new("ShaderNodeVectorMath")
    radius.label = "Distance from center"
    radius.operation = "LENGTH"
    radius.location = (-680, -220)
    links.new(position.outputs["Position"], radius.inputs[0])

    phase = nodes.new("ShaderNodeMath")
    phase.label = "Wave frequency"
    phase.operation = "MULTIPLY"
    phase.location = (-460, -220)
    phase.inputs[1].default_value = 1.85
    links.new(radius.outputs["Value"], phase.inputs[0])

    sine = nodes.new("ShaderNodeMath")
    sine.label = "Radial sine"
    sine.operation = "SINE"
    sine.location = (-240, -220)
    links.new(phase.outputs["Value"], sine.inputs[0])

    amplitude = nodes.new("ShaderNodeMath")
    amplitude.label = "Wave amplitude"
    amplitude.operation = "MULTIPLY"
    amplitude.location = (-20, -220)
    amplitude.inputs[1].default_value = 0.78
    links.new(sine.outputs["Value"], amplitude.inputs[0])

    offset = nodes.new("ShaderNodeCombineXYZ")
    offset.label = "Z offset"
    offset.location = (200, -220)
    links.new(amplitude.outputs["Value"], offset.inputs["Z"])

    set_position = nodes.new("GeometryNodeSetPosition")
    set_position.label = "Displace grid vertices"
    set_position.location = (-120, 100)
    links.new(grid.outputs["Mesh"], set_position.inputs["Geometry"])
    links.new(offset.outputs["Vector"], set_position.inputs["Offset"])

    points = nodes.new("GeometryNodeMeshToPoints")
    points.label = "Vertices to points"
    points.mode = "VERTICES"
    points.location = (120, 100)
    points.inputs["Radius"].default_value = 0.10
    links.new(set_position.outputs["Geometry"], points.inputs["Mesh"])

    ico = nodes.new("GeometryNodeMeshIcoSphere")
    ico.label = "Instance geometry"
    ico.location = (100, -90)
    ico.inputs["Radius"].default_value = 0.16
    ico.inputs["Subdivisions"].default_value = 2

    set_material = nodes.new("GeometryNodeSetMaterial")
    set_material.location = (330, -90)
    set_material.inputs["Material"].default_value = material
    links.new(ico.outputs["Mesh"], set_material.inputs["Geometry"])

    instances = nodes.new("GeometryNodeInstanceOnPoints")
    instances.label = "Instance on every grid vertex"
    instances.location = (380, 100)
    instances.inputs["Scale"].default_value = (0.82, 0.82, 0.82)
    links.new(points.outputs["Points"], instances.inputs["Points"])
    links.new(set_material.outputs["Geometry"], instances.inputs["Instance"])

    realize = nodes.new("GeometryNodeRealizeInstances")
    realize.label = "Real mesh output"
    realize.location = (650, 100)
    links.new(instances.outputs["Instances"], realize.inputs["Geometry"])

    group_output = nodes.new("NodeGroupOutput")
    group_output.location = (900, 100)
    group_output.is_active_output = True
    links.new(realize.outputs["Geometry"], group_output.inputs["Geometry"])

    modifier = host.modifiers.new(name="GeometryNodes", type="NODES")
    modifier.node_group = group
    return group


def evaluated_geometry_counts(obj) -> tuple[int, int, int]:
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        return len(mesh.vertices), len(mesh.edges), len(mesh.polygons)
    finally:
        evaluated.to_mesh_clear()


def build_scene() -> None:
    clear_scene()
    scene = bpy.context.scene
    engine = choose_engine(scene)

    scene.render.resolution_x = 768
    scene.render.resolution_y = 576
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.filepath = str(RENDER_PATH)

    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.006, 0.010, 0.020, 1.0)
    background.inputs["Strength"].default_value = 0.28

    ripple_mat = make_material("RippleMetal", (0.035, 0.42, 0.72), 0.72, 0.19)
    floor_mat = make_material("Floor", (0.025, 0.032, 0.050), 0.20, 0.36)

    host_mesh = bpy.data.meshes.new("GeometryNodesHostMesh")
    host_mesh.from_pydata([(0.0, 0.0, 0.0)], [], [])
    host_mesh.update()
    host = bpy.data.objects.new("GeometryNodesHost", host_mesh)
    bpy.context.collection.objects.link(host)
    group = build_geometry_nodes(host, ripple_mat)

    bpy.ops.mesh.primitive_plane_add(size=24.0, location=(0.0, 0.0, -1.25))
    floor = bpy.context.object
    floor.name = "Floor"
    floor.data.materials.append(floor_mat)

    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    camera.location = (9.6, -12.2, 9.2)
    camera_data.lens = 52.0
    camera_data.sensor_width = 36.0
    look_at(camera, (0.0, 0.0, -0.05))

    add_area_light("Key", (4.5, -3.5, 10.0), 1350.0, 5.5, (0.58, 0.78, 1.0))
    add_area_light("Fill", (-6.0, -1.0, 6.0), 900.0, 4.0, (0.28, 0.52, 1.0))
    add_area_light("Rim", (2.0, 7.0, 8.0), 1150.0, 4.0, (0.95, 0.44, 0.18))

    vertices, edges, polygons = evaluated_geometry_counts(host)
    node_types = [node.bl_idname for node in group.nodes]
    report = {
        "object": host.name,
        "modifier": "GeometryNodes",
        "node_group": group.name,
        "node_count": len(group.nodes),
        "node_types": node_types,
        "grid_vertices_x": GRID_VERTICES_X,
        "grid_vertices_y": GRID_VERTICES_Y,
        "grid_point_count": GRID_VERTICES_X * GRID_VERTICES_Y,
        "evaluated_vertices": vertices,
        "evaluated_edges": edges,
        "evaluated_polygons": polygons,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    bpy.ops.render.render(write_still=True)

    print(f"BLENDER_ENGINE={engine}")
    print(f"GN_NODE_COUNT={report['node_count']}")
    print(f"GN_EVALUATED_VERTICES={vertices}")
    print(f"GN_EVALUATED_POLYGONS={polygons}")
    print(f"BLEND_PATH={BLEND_PATH}")
    print(f"RENDER_PATH={RENDER_PATH}")


if __name__ == "__main__":
    build_scene()
