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
POINT_RADIUS = 0.034
COLORS = {
    "peer-soft-cube-drop": (0.88, 0.18, 0.38),
    "kugelstadt-stiff-cube-drop": (0.18, 0.48, 1.00),
    "cantilever-beam": (0.95, 0.58, 0.08),
    "fixed-column-kick": (0.14, 0.78, 0.48),
    "elastic-block-collision": (0.65, 0.30, 1.00)
}

def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--cache", type=Path, required=True)
    return p.parse_args(argv)

def to_blender(points):
    values = np.asarray(points, dtype=np.float32)
    out = np.empty_like(values)
    out[:, 0] = values[:, 0]
    out[:, 1] = -values[:, 2]
    out[:, 2] = values[:, 1]
    return out

def vec3_array(values):
    return Vt.Vec3fArray([Gf.Vec3f(float(x), float(y), float(z)) for x, y, z in values])

def look_at(obj, point):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat("-Z", "Y").to_euler()

def mat(name, color, roughness=0.30):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Metallic"].default_value = 0.03
    b.inputs["Roughness"].default_value = roughness
    e = b.inputs.get("Emission Color") or b.inputs.get("Emission")
    if e is not None:
        e.default_value = (*color, 1.0)
    s = b.inputs.get("Emission Strength")
    if s is not None:
        s.default_value = 0.07
    return m

def sock(collection, name):
    s = collection.get(name)
    if s is None:
        raise RuntimeError(f"missing socket {name}")
    return s

def prototype(material):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=POINT_RADIUS, location=(0,0,-10))
    o = bpy.context.object
    o.name = "ElasticPointPrototype"
    o.data.materials.append(material)
    o.hide_render = True
    o.display_type = "WIRE"
    return o

def geometry_nodes(obj, proto):
    g = bpy.data.node_groups.new("Elastic SPH Points", "GeometryNodeTree")
    g.is_modifier = True
    g.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    g.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    n = g.nodes
    l = g.links
    gi = n.new("NodeGroupInput")
    go = n.new("NodeGroupOutput")
    mtp = n.new("GeometryNodeMeshToPoints")
    mtp.mode = "VERTICES"
    oi = n.new("GeometryNodeObjectInfo")
    sock(oi.inputs, "Object").default_value = proto
    inst = n.new("GeometryNodeInstanceOnPoints")
    real = n.new("GeometryNodeRealizeInstances")
    l.new(sock(gi.outputs, "Geometry"), sock(mtp.inputs, "Mesh"))
    l.new(sock(mtp.outputs, "Points"), sock(inst.inputs, "Points"))
    l.new(sock(oi.outputs, "Geometry"), sock(inst.inputs, "Instance"))
    l.new(sock(inst.outputs, "Instances"), sock(real.inputs, "Geometry"))
    l.new(sock(real.outputs, "Geometry"), sock(go.inputs, "Geometry"))
    mod = obj.modifiers.new("Elastic SPH Geometry Nodes", "NODES")
    mod.node_group = g
    return g

def author_usd(cache, manifest, path):
    stage = Usd.Stage.CreateNew(str(path))
    stage.SetStartTimeCode(1)
    stage.SetEndTimeCode(manifest["frames"])
    stage.SetFramesPerSecond(manifest["fps"])
    stage.SetTimeCodesPerSecond(manifest["fps"])
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    mesh = UsdGeom.Mesh.Define(stage, "/ElasticPoints")
    mesh.CreateSubdivisionSchemeAttr().Set(UsdGeom.Tokens.none)
    mesh.CreateFaceVertexCountsAttr().Set(Vt.IntArray([]))
    mesh.CreateFaceVertexIndicesAttr().Set(Vt.IntArray([]))
    attr = mesh.CreatePointsAttr()
    t0 = time.perf_counter()
    for rec in manifest["frames_data"]:
        pts = np.load(cache / rec["file"])["points"]
        attr.Set(vec3_array(to_blender(pts)), Usd.TimeCode(int(rec["sequence_frame"])))
    stage.GetRootLayer().Save()
    return time.perf_counter() - t0

def main():
    args = parse_args()
    cache = args.cache.resolve()
    manifest = json.loads((cache / "manifest.json").read_text())
    base = ROOT / "output" / f"sph-elastic-{args.case}"
    base.mkdir(parents=True, exist_ok=True)
    usd_path = base / "elastic-points.usdc"
    blend_path = base / f"sph-elastic-{args.case}.blend"
    preview_path = base / "preview.png"
    video_path = base / "media.mp4"
    validation_path = base / "validation.json"

    usd_seconds = author_usd(cache, manifest, usd_path)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    t0 = time.perf_counter()
    result = bpy.ops.wm.usd_import(
        filepath=str(usd_path), set_frame_range=False,
        import_cameras=False, import_curves=False, import_lights=False,
        import_materials=False, import_meshes=True, import_volumes=False
    )
    import_seconds = time.perf_counter() - t0
    if "FINISHED" not in result:
        raise RuntimeError(result)

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = int(manifest["frames"])
    scene.render.fps = int(manifest["fps"])

    obj = bpy.data.objects.get("ElasticPoints")
    if obj is None:
        raise RuntimeError("ElasticPoints missing")

    material = mat("ElasticMaterial", COLORS.get(args.case, (0.3, 0.7, 1.0)))
    group = geometry_nodes(obj, prototype(material))

    floor_mat = mat("Floor", (0.025,0.035,0.05), 0.65)
    bpy.ops.mesh.primitive_plane_add(size=8.0, location=(0,0,0))
    floor = bpy.context.object
    floor.data.materials.append(floor_mat)

    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.006,0.010,0.022,1)
    bg.inputs["Strength"].default_value = 0.25

    for name, loc, energy, size, color in (
        ("Key",(4,-4,5.5),900,4,(1.0,0.82,0.65)),
        ("Fill",(-3,-1,4),550,3,(0.45,0.68,1.0)),
        ("Rim",(0,4,5),700,3,(0.55,0.85,1.0))
    ):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size, ld.color = energy, size, color
        lo = bpy.data.objects.new(name, ld)
        bpy.context.collection.objects.link(lo)
        lo.location = loc
        look_at(lo, (0,0,0.9))

    camd = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", camd)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    cam.location = (4.9,-7.5,3.6)
    camd.lens = 50
    look_at(cam, (0,0,0.9))

    for engine in ("BLENDER_EEVEE_NEXT","BLENDER_EEVEE","BLENDER_WORKBENCH"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            pass
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100

    required = {"GeometryNodeMeshToPoints","GeometryNodeObjectInfo","GeometryNodeInstanceOnPoints","GeometryNodeRealizeInstances"}
    nodes = {node.bl_idname for node in group.nodes}
    errors = []
    if required - nodes:
        errors.append(f"missing nodes: {sorted(required-nodes)}")

    deps = bpy.context.evaluated_depsgraph_get()
    checks = []
    check_frames = sorted(set([1, max(1,manifest["frames"]//4), max(1,manifest["frames"]//2), max(1,3*manifest["frames"]//4), manifest["frames"]]))
    for frame in check_frames:
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        deps.update()
        ev = obj.evaluated_get(deps)
        mesh = ev.to_mesh()
        try:
            v, f = len(mesh.vertices), len(mesh.polygons)
        finally:
            ev.to_mesh_clear()
        if v <= manifest["particle_count"] or f <= 0:
            errors.append(f"frame {frame}: invalid GN geometry {v}/{f}")
        checks.append({"frame": frame, "vertices": v, "faces": f})

    if errors:
        raise RuntimeError("; ".join(errors))

    scene.frame_set(max(1, manifest["frames"]//2))
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(preview_path)
    bpy.ops.render.render(write_still=True)

    scene.frame_set(1)
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.filepath = str(video_path)
    rt = time.perf_counter()
    bpy.ops.render.render(animation=True)
    render_seconds = time.perf_counter() - rt

    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    for cf in bpy.data.cache_files:
        cf.filepath = "//elastic-points.usdc"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    first = manifest["frames_data"][0]
    last = manifest["frames_data"][-1]
    validation = {
        "case": args.case,
        "representation": "elastic-sph-to-animated-usd-plus-geometry-nodes",
        "frames": manifest["frames"],
        "fps": manifest["fps"],
        "particle_count": manifest["particle_count"],
        "velocity_stats": manifest["velocity_stats"],
        "first_extent": first["extent"],
        "last_extent": last["extent"],
        "last_extent_ratio": last["extent_ratio"],
        "first_centroid": first["centroid"],
        "last_centroid": last["centroid"],
        "point_npz_total_bytes": manifest["point_npz_total_bytes"],
        "point_usd_bytes": usd_path.stat().st_size,
        "blend_bytes": blend_path.stat().st_size,
        "preview_bytes": preview_path.stat().st_size,
        "video_bytes": video_path.stat().st_size,
        "usd_author_seconds": usd_seconds,
        "usd_import_seconds": import_seconds,
        "render_seconds": render_seconds,
        "geometry_nodes": {"point_radius": POINT_RADIUS, "nodes": sorted(nodes), "modifier_stack": [m.type for m in obj.modifiers]},
        "checks": checks,
        "errors": errors
    }
    validation_path.write_text(json.dumps(validation, indent=2) + "\n")
    print(json.dumps(validation, indent=2))

if __name__ == "__main__":
    main()
