from __future__ import annotations

import json
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path.cwd()
OUTPUT_DIR = ROOT / "output"
ASSET_DIR = ROOT / ".cache" / "quaternius-rpg-character-pack"

EXPERIMENT = "rpg-character-motion-showreel-long-eevee"
BLEND_PATH = OUTPUT_DIR / f"{EXPERIMENT}.blend"
REPORT_PATH = OUTPUT_DIR / f"{EXPERIMENT}-report.json"

FPS = 24
SEGMENT_FRAMES = 144
EXPECTED_ACTIONS = 13
FRAME_START = 1
FRAME_END = EXPECTED_ACTIONS * SEGMENT_FRAMES
RES_X = 480
RES_Y = 360
PREVIEW_FRAME = FRAME_END // 2


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


def material(name, color, roughness=0.5, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    return mat


def score(path):
    name = path.stem.lower()
    value = 0
    for rank, token in enumerate(("warrior", "knight", "ranger", "rogue", "cleric", "monk", "wizard")):
        if token in name:
            value += 100 - rank * 5
            break
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
        raise RuntimeError("no glTF/GLB/FBX character assets were downloaded")
    candidates.sort(key=score, reverse=True)
    print("ASSET_CANDIDATES=" + ",".join(p.name for p in candidates[:12]))
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


def normalize(imported, meshes):
    bpy.context.view_layer.update()
    mins, maxs = bounds(meshes)
    height = maxs.z - mins.z
    if height <= 1e-6:
        raise RuntimeError("invalid character height")
    scale = 2.6 / height
    center = (mins + maxs) * 0.5
    root = bpy.data.objects.new("CharacterRoot", None)
    bpy.context.collection.objects.link(root)
    for obj in [o for o in imported if o.parent is None]:
        world = obj.matrix_world.copy()
        obj.parent = root
        obj.matrix_world = world
    root.scale = (scale, scale, scale)
    root.location = (-center.x * scale, -center.y * scale, -mins.z * scale)
    bpy.context.view_layer.update()
    return root, scale


def action_sort_key(action):
    name = action.name.lower()
    preferred = ("idle", "walk", "run", "attack", "hit", "death", "jump")
    bucket = next((i for i, token in enumerate(preferred) if token in name), len(preferred))
    return bucket, name


def schedule_actions(armatures):
    actions = sorted(list(bpy.data.actions), key=action_sort_key)
    if len(actions) != EXPECTED_ACTIONS:
        raise RuntimeError(f"expected {EXPECTED_ACTIONS} imported actions, got {len(actions)}")

    armature = armatures[0]
    armature.animation_data_create()
    anim = armature.animation_data
    anim.action = None
    for track in list(anim.nla_tracks):
        anim.nla_tracks.remove(track)

    track = anim.nla_tracks.new()
    track.name = "LongMotionShowreel"

    segments = []
    for index, action in enumerate(actions):
        start = FRAME_START + index * SEGMENT_FRAMES
        end = start + SEGMENT_FRAMES - 1
        action_start = float(action.frame_range[0])
        action_end = float(action.frame_range[1])
        native_span = max(1.0, action_end - action_start)

        strip = track.strips.new(action.name, start, action)
        strip.name = f"{index + 1:02d}_{action.name}"
        strip.action_frame_start = action_start
        strip.action_frame_end = action_end
        strip.blend_type = "REPLACE"
        strip.extrapolation = "NOTHING"
        strip.repeat = SEGMENT_FRAMES / native_span

        segments.append({
            "index": index + 1,
            "action": action.name,
            "segment_start": start,
            "segment_end": end,
            "segment_frames": SEGMENT_FRAMES,
            "native_action_start": round(action_start, 3),
            "native_action_end": round(action_end, 3),
            "native_span": round(native_span, 3),
            "repeat": round(float(strip.repeat), 6),
        })

    return armature, actions, segments


def make_stage():
    floor_mat = material("Floor", (0.035, 0.045, 0.060), 0.72, 0.06)
    ring_mat = material("Ring", (0.10, 0.20, 0.28), 0.30, 0.58)
    bpy.ops.mesh.primitive_plane_add(size=14.0, location=(0, 0, 0))
    bpy.context.object.data.materials.append(floor_mat)
    bpy.ops.mesh.primitive_torus_add(
        major_radius=1.7, minor_radius=0.035,
        major_segments=96, minor_segments=12,
        location=(0, 0, 0.025),
    )
    bpy.context.object.data.materials.append(ring_mat)


def setup_camera(scene):
    data = bpy.data.cameras.new("Camera")
    cam = bpy.data.objects.new("Camera", data)
    bpy.context.collection.objects.link(cam)
    scene.camera = cam
    cam.location = (4.8, -6.8, 3.25)
    data.lens = 58.0
    look_at(cam, (0, 0, 1.25))


def light(name, location, energy, size, color):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, (0, 0, 1.3))


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
    bg.inputs["Color"].default_value = (0.006, 0.009, 0.016, 1)
    bg.inputs["Strength"].default_value = 0.12

    source = find_asset()
    imported, meshes, armatures = import_character(source)
    root, normal_scale = normalize(imported, meshes)
    armature, actions, segments = schedule_actions(armatures)

    make_stage()
    setup_camera(scene)
    light("Key", (-3.8, -4.2, 6.5), 1100, 4.2, (1.0, 0.82, 0.66))
    light("Fill", (4.5, -1.0, 4.5), 650, 3.8, (0.50, 0.72, 1.0))
    light("Rim", (1.0, 4.0, 5.8), 850, 3.0, (0.58, 0.82, 1.0))

    try:
        bpy.ops.file.pack_all()
    except Exception as exc:
        print(f"PACK_WARNING={exc}")

    scene.frame_set(PREVIEW_FRAME)
    bpy.context.view_layer.update()
    mins, maxs = bounds(meshes)
    height = maxs.z - mins.z
    materials = {slot.material for obj in meshes for slot in obj.material_slots if slot.material}
    images = [img for img in bpy.data.images if img.name != "Render Result"]

    report = {
        "experiment": EXPERIMENT,
        "engine": engine,
        "frame_start": FRAME_START,
        "frame_end": FRAME_END,
        "fps": FPS,
        "duration_seconds": FRAME_END / FPS,
        "segment_frames": SEGMENT_FRAMES,
        "scheduled_action_count": len(segments),
        "resolution_x": RES_X,
        "resolution_y": RES_Y,
        "requested_render_samples": 24,
        "effective_render_samples": samples,
        "source": {
            "publisher": "Quaternius",
            "pack": "RPG Character Pack",
            "license": "CC0 1.0",
            "pack_page": "https://quaternius.com/packs/rpgcharacters.html",
            "drive_folder": "https://drive.google.com/drive/folders/1MIRQXLfTd21HMI5rwOb6Xy0rv0xv1m8b?usp=sharing",
            "asset_file": source.name,
            "asset_format": source.suffix.lower(),
        },
        "character": {
            "imported_object_count": len(imported),
            "mesh_count": len(meshes),
            "armature_count": len(armatures),
            "action_count": len(actions),
            "scheduled_action_count": len(segments),
            "scheduled_action_names": [segment["action"] for segment in segments],
            "selected_armature": armature.name,
            "material_count": len(materials),
            "image_count": len(images),
            "normalize_scale": round(normal_scale, 6),
            "preview_height": round(height, 6),
            "root": root.name,
        },
        "segments": segments,
        "blend": BLEND_PATH.name,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    scene.frame_set(FRAME_START)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

    print(f"BLENDER_ENGINE={engine}")
    print(f"CHARACTER_SOURCE={source}")
    print(f"CHARACTER_ACTIONS={len(actions)}")
    print("CHARACTER_ACTION_NAMES=" + " | ".join(a.name for a in actions))
    print(f"SHOWREEL_FRAMES={FRAME_START}-{FRAME_END}")
    print(f"SHOWREEL_SECONDS={FRAME_END / FPS:.1f}")
    print(f"BLEND_PATH={BLEND_PATH}")


if __name__ == "__main__":
    build_scene()
