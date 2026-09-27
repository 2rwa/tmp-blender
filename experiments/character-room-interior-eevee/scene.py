from __future__ import annotations

import json
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path.cwd()
OUTPUT_DIR = ROOT / "output"
ASSET_DIR = ROOT / ".cache" / "quaternius-rpg-character-pack"

EXPERIMENT = "character-room-interior-eevee"
BLEND_PATH = OUTPUT_DIR / f"{EXPERIMENT}.blend"
REPORT_PATH = OUTPUT_DIR / f"{EXPERIMENT}-report.json"

FRAME_START = 1
FRAME_END = 360
FPS = 24
RES_X = 480
RES_Y = 360
PREVIEW_FRAME = 180

ROOM_WIDTH = 7.2
ROOM_DEPTH = 5.4
ROOM_HEIGHT = 3.0
WALL = 0.12
CHARACTER_HEIGHT = 1.78


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def choose_engine(scene):
    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        try:
            scene.render.engine = candidate
            return candidate
        except TypeError:
            pass
    scene.render.engine = "BLENDER_WORKBENCH"
    return "BLENDER_WORKBENCH"


def configure_render(scene):
    eevee = getattr(scene, "eevee", None)
    if eevee is not None and hasattr(eevee, "taa_render_samples"):
        eevee.taa_render_samples = 24
        if hasattr(eevee, "use_gtao"):
            eevee.use_gtao = True
        return int(eevee.taa_render_samples)
    return None


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def make_material(name, color, roughness=0.5, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def add_box(name, size, location, material, bevel=0.03):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material is not None:
        obj.data.materials.append(material)
    if bevel > 0:
        mod = obj.modifiers.new(name="SoftEdges", type="BEVEL")
        mod.width = bevel
        mod.segments = 2
    return obj


def add_cylinder(name, radius, depth, location, material, vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    if material is not None:
        obj.data.materials.append(material)
    mod = obj.modifiers.new(name="SoftEdges", type="BEVEL")
    mod.width = 0.02
    mod.segments = 2
    return obj


def score_asset(path):
    name = path.stem.lower()
    value = 100 if "warrior" in name else 0
    if any(token in name for token in ("weapon", "sword", "bow", "staff", "axe", "shield")):
        value -= 100
    value += {".glb": 30, ".gltf": 20, ".fbx": 10}.get(path.suffix.lower(), 0)
    return value, str(path).lower()


def find_asset():
    candidates = [
        p for p in ASSET_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() in {".glb", ".gltf", ".fbx"}
    ]
    if not candidates:
        raise RuntimeError("no character asset downloaded")
    candidates.sort(key=score_asset, reverse=True)
    return candidates[0]


def import_character(path):
    before = set(bpy.data.objects)
    if path.suffix.lower() in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    else:
        bpy.ops.import_scene.fbx(filepath=str(path), use_anim=True)
    imported = [obj for obj in bpy.data.objects if obj not in before]
    meshes = [obj for obj in imported if obj.type == "MESH"]
    armatures = [obj for obj in imported if obj.type == "ARMATURE"]
    if not meshes or not armatures:
        raise RuntimeError(f"bad character import: meshes={len(meshes)} armatures={len(armatures)}")
    return imported, meshes, armatures


def bounds(meshes):
    points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    mins = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    maxs = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return mins, maxs


def normalize_character(imported, meshes):
    bpy.context.view_layer.update()
    mins, maxs = bounds(meshes)
    height = maxs.z - mins.z
    if height <= 1e-6:
        raise RuntimeError("invalid character height")
    scale = CHARACTER_HEIGHT / height
    center = (mins + maxs) * 0.5
    root = bpy.data.objects.new("CharacterRoot", None)
    bpy.context.collection.objects.link(root)
    for obj in [o for o in imported if o.parent is None]:
        world = obj.matrix_world.copy()
        obj.parent = root
        obj.matrix_world = world
    root.scale = (scale, scale, scale)
    root.location = (-center.x * scale + 0.55, -center.y * scale - 0.15, -mins.z * scale)
    bpy.context.view_layer.update()
    return root, scale


def choose_idle(armatures):
    actions = list(bpy.data.actions)
    if not actions:
        raise RuntimeError("no animation actions imported")
    action = next((a for a in actions if "idle" in a.name.lower()), actions[0])
    armature = armatures[0]
    armature.animation_data_create()
    armature.animation_data.action = action
    for fc in action.fcurves:
        try:
            fc.modifiers.new(type="CYCLES")
        except Exception:
            pass
    return armature, action, actions


def make_room():
    wall_mat = make_material("WarmWall", (0.56, 0.53, 0.48), 0.82)
    ceiling_mat = make_material("Ceiling", (0.73, 0.72, 0.68), 0.90)
    wood_mat = make_material("WarmWood", (0.22, 0.105, 0.045), 0.48)
    dark_wood = make_material("DarkWood", (0.075, 0.045, 0.030), 0.42)
    fabric = make_material("SofaFabric", (0.10, 0.25, 0.21), 0.92)
    rug_mat = make_material("Rug", (0.30, 0.12, 0.085), 0.96)
    metal = make_material("Metal", (0.08, 0.09, 0.10), 0.30, 0.55)
    window_mat = make_material("WindowGlass", (0.12, 0.28, 0.40), 0.16, 0.18)
    screen_mat = make_material("MonitorScreen", (0.018, 0.035, 0.055), 0.18, 0.08)
    accent = make_material("WallArt", (0.43, 0.22, 0.10), 0.55)

    room_objects = []
    furniture_objects = []
    decor_objects = []

    def room_box(name, size, location, mat, bevel=0.02):
        obj = add_box(name, size, location, mat, bevel)
        room_objects.append(obj)
        return obj

    def furniture_box(name, size, location, mat, bevel=0.035):
        obj = add_box(name, size, location, mat, bevel)
        furniture_objects.append(obj)
        return obj

    room_box("Floor", (ROOM_WIDTH, ROOM_DEPTH, 0.12), (0, 0, -0.06), wood_mat, 0.01)
    room_box("Ceiling", (ROOM_WIDTH, ROOM_DEPTH, 0.10), (0, 0, ROOM_HEIGHT + 0.05), ceiling_mat, 0.01)
    room_box("LeftWall", (WALL, ROOM_DEPTH, ROOM_HEIGHT), (-ROOM_WIDTH / 2, 0, ROOM_HEIGHT / 2), wall_mat, 0.01)
    room_box("RightWall", (WALL, ROOM_DEPTH, ROOM_HEIGHT), (ROOM_WIDTH / 2, 0, ROOM_HEIGHT / 2), wall_mat, 0.01)

    window_width = 2.2
    window_height = 1.4
    sill_z = 0.9
    side_width = (ROOM_WIDTH - window_width) / 2
    room_box("BackWallLeft", (side_width, WALL, ROOM_HEIGHT), (-(window_width + side_width) / 2, ROOM_DEPTH / 2, ROOM_HEIGHT / 2), wall_mat, 0.01)
    room_box("BackWallRight", (side_width, WALL, ROOM_HEIGHT), ((window_width + side_width) / 2, ROOM_DEPTH / 2, ROOM_HEIGHT / 2), wall_mat, 0.01)
    room_box("BackWallBelowWindow", (window_width, WALL, sill_z), (0, ROOM_DEPTH / 2, sill_z / 2), wall_mat, 0.01)
    top_h = ROOM_HEIGHT - (sill_z + window_height)
    room_box("BackWallAboveWindow", (window_width, WALL, top_h), (0, ROOM_DEPTH / 2, sill_z + window_height + top_h / 2), wall_mat, 0.01)

    frame_depth = 0.08
    frame = 0.08
    window_y = ROOM_DEPTH / 2 - WALL / 2 - 0.025
    for name, size, location in (
        ("WindowFrameLeft", (frame, frame_depth, window_height), (-window_width / 2 + frame / 2, window_y, sill_z + window_height / 2)),
        ("WindowFrameRight", (frame, frame_depth, window_height), (window_width / 2 - frame / 2, window_y, sill_z + window_height / 2)),
        ("WindowFrameBottom", (window_width, frame_depth, frame), (0, window_y, sill_z + frame / 2)),
        ("WindowFrameTop", (window_width, frame_depth, frame), (0, window_y, sill_z + window_height - frame / 2)),
    ):
        decor_objects.append(add_box(name, size, location, dark_wood, 0.015))
    decor_objects.append(add_box("WindowGlass", (window_width - 0.14, 0.025, window_height - 0.14), (0, window_y + 0.025, sill_z + window_height / 2), window_mat, 0.005))
    decor_objects.append(add_box("WindowSill", (window_width + 0.24, 0.32, 0.07), (0, ROOM_DEPTH / 2 - 0.13, sill_z - 0.02), dark_wood, 0.02))

    door_x = -ROOM_WIDTH / 2 + WALL / 2 + 0.025
    door_y = -1.0
    decor_objects.append(add_box("DoorPanel", (0.055, 1.02, 2.08), (door_x + 0.015, door_y, 1.04), dark_wood, 0.03))
    decor_objects.append(add_box("DoorTrimFront", (0.07, 0.08, 2.18), (door_x + 0.04, door_y - 0.55, 1.09), wood_mat, 0.01))
    decor_objects.append(add_box("DoorTrimBack", (0.07, 0.08, 2.18), (door_x + 0.04, door_y + 0.55, 1.09), wood_mat, 0.01))
    decor_objects.append(add_box("DoorTrimTop", (0.07, 1.18, 0.08), (door_x + 0.04, door_y, 2.14), wood_mat, 0.01))

    furniture_box("Rug", (3.6, 2.45, 0.035), (-0.55, -0.25, 0.02), rug_mat, 0.025)

    sofa_x, sofa_y = -2.15, 0.65
    furniture_box("SofaBase", (2.35, 0.88, 0.28), (sofa_x, sofa_y, 0.30), fabric, 0.08)
    furniture_box("SofaSeat", (2.18, 0.72, 0.18), (sofa_x, sofa_y - 0.04, 0.51), fabric, 0.07)
    furniture_box("SofaBack", (2.35, 0.22, 0.88), (sofa_x, sofa_y + 0.38, 0.90), fabric, 0.08)
    furniture_box("SofaArmL", (0.20, 0.88, 0.58), (sofa_x - 1.08, sofa_y, 0.57), fabric, 0.07)
    furniture_box("SofaArmR", (0.20, 0.88, 0.58), (sofa_x + 1.08, sofa_y, 0.57), fabric, 0.07)

    table_x, table_y = -1.35, -0.55
    furniture_box("CoffeeTableTop", (1.55, 0.78, 0.10), (table_x, table_y, 0.46), wood_mat, 0.04)
    for ix in (-0.65, 0.65):
        for iy in (-0.28, 0.28):
            furniture_box(f"CoffeeTableLeg_{ix}_{iy}", (0.09, 0.09, 0.42), (table_x + ix, table_y + iy, 0.21), dark_wood, 0.02)

    desk_x, desk_y = 2.15, 1.62
    furniture_box("DeskTop", (1.85, 0.72, 0.11), (desk_x, desk_y, 0.77), wood_mat, 0.035)
    for ix in (-0.78, 0.78):
        for iy in (-0.27, 0.27):
            furniture_box(f"DeskLeg_{ix}_{iy}", (0.08, 0.08, 0.72), (desk_x + ix, desk_y + iy, 0.36), metal, 0.015)
    furniture_box("MonitorScreen", (0.95, 0.08, 0.58), (desk_x, desk_y + 0.12, 1.23), screen_mat, 0.035)
    furniture_box("MonitorStand", (0.12, 0.12, 0.28), (desk_x, desk_y + 0.10, 0.94), metal, 0.02)
    furniture_box("Keyboard", (0.72, 0.25, 0.035), (desk_x, desk_y - 0.17, 0.85), metal, 0.02)

    chair_x, chair_y = 2.10, 0.72
    furniture_box("ChairSeat", (0.58, 0.56, 0.11), (chair_x, chair_y, 0.48), fabric, 0.04)
    furniture_box("ChairBack", (0.58, 0.11, 0.70), (chair_x, chair_y + 0.25, 0.83), fabric, 0.04)
    for ix in (-0.23, 0.23):
        for iy in (-0.21, 0.21):
            furniture_box(f"ChairLeg_{ix}_{iy}", (0.055, 0.055, 0.43), (chair_x + ix, chair_y + iy, 0.215), metal, 0.012)

    shelf_x, shelf_y = 3.22, 0.55
    furniture_box("BookshelfBack", (0.16, 1.55, 2.20), (shelf_x, shelf_y, 1.10), dark_wood, 0.025)
    for z in (0.10, 0.52, 0.94, 1.36, 1.78, 2.16):
        furniture_box(f"BookshelfShelf_{z}", (0.48, 1.55, 0.07), (shelf_x - 0.18, shelf_y, z), wood_mat, 0.018)
    furniture_box("BookshelfSideFront", (0.48, 0.08, 2.20), (shelf_x - 0.18, shelf_y - 0.74, 1.10), wood_mat, 0.018)
    furniture_box("BookshelfSideBack", (0.48, 0.08, 2.20), (shelf_x - 0.18, shelf_y + 0.74, 1.10), wood_mat, 0.018)

    lamp_x, lamp_y = -3.0, -0.65
    furniture_objects.append(add_cylinder("FloorLampBase", 0.25, 0.06, (lamp_x, lamp_y, 0.03), metal))
    furniture_objects.append(add_cylinder("FloorLampPole", 0.035, 1.55, (lamp_x, lamp_y, 0.80), metal, 24))
    furniture_objects.append(add_cylinder("FloorLampShade", 0.27, 0.34, (lamp_x, lamp_y, 1.62), ceiling_mat, 32))

    decor_objects.append(add_box("WallArt", (1.05, 0.055, 0.72), (-2.25, ROOM_DEPTH / 2 - 0.08, 1.80), accent, 0.025))
    decor_objects.append(add_box("CeilingPanel", (1.00, 0.62, 0.055), (0, -0.15, ROOM_HEIGHT - 0.08), ceiling_mat, 0.03))

    return {
        "room_objects": room_objects,
        "furniture_objects": furniture_objects,
        "decor_objects": decor_objects,
        "furniture_groups": ["rug", "sofa", "coffee_table", "desk", "chair", "bookshelf", "floor_lamp"],
        "window_opening": {"width": window_width, "height": window_height, "sill_z": sill_z},
    }


def add_area_light(name, location, energy, size, color, target):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, target)
    return obj


def add_point_light(name, location, energy, color):
    data = bpy.data.lights.new(name=name, type="POINT")
    data.energy = energy
    data.color = color
    data.shadow_soft_size = 0.55
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    return obj


def setup_lighting():
    return [
        add_area_light("CeilingArea", (0, -0.15, 2.78), 650, 2.5, (1.0, 0.83, 0.66), (0, -0.1, 0.6)),
        add_area_light("WindowArea", (0, 2.30, 1.75), 900, 2.2, (0.48, 0.68, 1.0), (0, 0.2, 1.1)),
        add_area_light("FrontFill", (0.0, -4.8, 2.5), 450, 3.5, (0.70, 0.80, 1.0), (0, 0.4, 1.1)),
        add_point_light("FloorLampLight", (-3.0, -0.65, 1.55), 170, (1.0, 0.55, 0.28)),
    ]


def setup_camera(scene):
    data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    keyframes = (
        (1, (0.0, -7.4, 1.95), (0.0, 0.30, 1.20), 35.0),
        (120, (-3.35, -5.55, 2.15), (-0.75, 0.45, 1.10), 38.0),
        (240, (3.45, -5.25, 2.35), (0.65, 0.75, 1.20), 39.0),
        (360, (0.85, -6.35, 1.72), (0.20, 0.25, 1.05), 36.0),
    )
    for frame, location, target, lens in keyframes:
        cam.location = location
        data.lens = lens
        look_at(cam, target)
        cam.keyframe_insert(data_path="location", frame=frame)
        cam.keyframe_insert(data_path="rotation_euler", frame=frame)
        data.keyframe_insert(data_path="lens", frame=frame)
    return cam, len(keyframes)


def build_scene():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    clear_scene()

    scene = bpy.context.scene
    engine = choose_engine(scene)
    samples = configure_render(scene)
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END
    scene.render.fps = FPS
    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"

    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.012, 0.017, 0.026, 1)
    bg.inputs["Strength"].default_value = 0.15

    room = make_room()

    source = find_asset()
    imported, meshes, armatures = import_character(source)
    root, normal_scale = normalize_character(imported, meshes)
    armature, action, actions = choose_idle(armatures)

    lights = setup_lighting()
    camera, camera_keyframes = setup_camera(scene)

    try:
        bpy.ops.file.pack_all()
    except Exception as exc:
        print(f"PACK_WARNING={exc}")

    scene.frame_set(PREVIEW_FRAME)
    bpy.context.view_layer.update()
    mins, maxs = bounds(meshes)
    char_height = maxs.z - mins.z
    materials = {slot.material for obj in meshes for slot in obj.material_slots if slot.material}
    images = [img for img in bpy.data.images if img.name != "Render Result"]
    mesh_objects = [obj for obj in bpy.data.objects if obj.type == "MESH"]

    report = {
        "experiment": EXPERIMENT,
        "engine": engine,
        "frame_start": FRAME_START,
        "frame_end": FRAME_END,
        "fps": FPS,
        "duration_seconds": FRAME_END / FPS,
        "resolution_x": RES_X,
        "resolution_y": RES_Y,
        "requested_render_samples": 24,
        "effective_render_samples": samples,
        "room": {
            "width_m": ROOM_WIDTH,
            "depth_m": ROOM_DEPTH,
            "height_m": ROOM_HEIGHT,
            "open_front": True,
            "room_mesh_count": len(room["room_objects"]),
            "furniture_object_count": len(room["furniture_objects"]),
            "decor_object_count": len(room["decor_objects"]),
            "furniture_groups": room["furniture_groups"],
            "window_opening": room["window_opening"],
            "light_count": len(lights),
            "camera_keyframes": camera_keyframes,
            "total_scene_mesh_count": len(mesh_objects),
        },
        "source": {
            "publisher": "Quaternius",
            "pack": "RPG Character Pack",
            "license": "CC0 1.0",
            "asset_file": source.name,
            "asset_format": source.suffix.lower(),
        },
        "character": {
            "target_height_m": CHARACTER_HEIGHT,
            "preview_height_m": round(char_height, 6),
            "normalize_scale": round(normal_scale, 6),
            "mesh_count": len(meshes),
            "armature_count": len(armatures),
            "action_count": len(actions),
            "selected_action": action.name,
            "selected_armature": armature.name,
            "material_count": len(materials),
            "image_count": len(images),
            "root": root.name,
        },
        "camera": camera.name,
        "blend": BLEND_PATH.name,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    scene.frame_set(FRAME_START)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

    print(f"BLENDER_ENGINE={engine}")
    print(f"ROOM_DIMENSIONS={ROOM_WIDTH}x{ROOM_DEPTH}x{ROOM_HEIGHT}")
    print(f"ROOM_MESHES={len(room['room_objects'])}")
    print(f"FURNITURE_OBJECTS={len(room['furniture_objects'])}")
    print(f"DECOR_OBJECTS={len(room['decor_objects'])}")
    print(f"CHARACTER_ACTION={action.name}")
    print(f"CHARACTER_HEIGHT={char_height:.4f}")
    print(f"BLEND_PATH={BLEND_PATH}")


if __name__ == "__main__":
    build_scene()
