from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path.cwd()
OUTPUT_DIR = ROOT / "output"
ANALYSIS_PATH = OUTPUT_DIR / "music-sync-analysis.json"

EXPERIMENT = "audio-reactive-music-20260928"
BLEND_PATH = OUTPUT_DIR / f"{EXPERIMENT}.blend"
REPORT_PATH = OUTPUT_DIR / f"{EXPERIMENT}-report.json"

FPS = 24
FRAME_START = 1
FRAME_END = 480
RES_X = 480
RES_Y = 360
BAR_COUNT = 36


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


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
        eevee.taa_render_samples = 16
        if hasattr(eevee, "use_gtao"):
            eevee.use_gtao = True
        return int(eevee.taa_render_samples)
    return None


def material(name: str, color: tuple[float, float, float], metallic: float, roughness: float):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        if "Base Color" in bsdf.inputs:
            bsdf.inputs["Base Color"].default_value = (*color, 1.0)
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = metallic
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = roughness
    mat.diffuse_color = (*color, 1.0)
    return mat


def look_at(obj, target=(0.0, 0.0, 1.25)) -> None:
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def linearize(obj) -> None:
    data = obj.animation_data
    if not data or not data.action:
        return
    for fcurve in data.action.fcurves:
        for point in fcurve.keyframe_points:
            point.interpolation = "LINEAR"


def add_bar(index: int, radius: float, mat):
    angle = math.tau * index / BAR_COUNT
    x = radius * math.cos(angle)
    y = radius * math.sin(angle)
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, y, 0.5))
    obj = bpy.context.object
    obj.name = f"AudioBar_{index:02d}"
    obj.dimensions = (0.24, 0.52, 1.0)
    obj.rotation_euler[2] = angle
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def add_ring(name: str, major_radius: float, minor_radius: float, z: float, mat):
    bpy.ops.mesh.primitive_torus_add(
        major_radius=major_radius,
        minor_radius=minor_radius,
        major_segments=96,
        minor_segments=12,
        location=(0.0, 0.0, z),
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return obj


def add_area_light(name: str, location, color, energy: float, size: float):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.color = color
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    look_at(obj, (0, 0, 1.0))
    return obj


def animate_scene(scene, frames, bars, core, rings, lights, camera) -> dict:
    keyframe_counter = 0

    for sample in frames:
        frame = int(sample["frame"])
        full = float(sample["full"])
        low = float(sample["low"])
        mid = float(sample["mid"])
        high = float(sample["high"])
        transient = float(sample["transient"])

        for i, bar in enumerate(bars):
            sector = i % 3
            if sector == 0:
                weighted = 0.72 * low + 0.18 * mid + 0.10 * high
            elif sector == 1:
                weighted = 0.15 * low + 0.70 * mid + 0.15 * high
            else:
                weighted = 0.08 * low + 0.22 * mid + 0.70 * high

            ripple = 0.5 + 0.5 * math.sin((i / BAR_COUNT) * math.tau * 3.0 + frame * 0.075)
            height = 0.28 + 2.6 * weighted + 0.55 * transient * ripple
            bar.scale.z = height
            bar.location.z = 0.5 * height
            bar.keyframe_insert(data_path="scale", index=2, frame=frame)
            bar.keyframe_insert(data_path="location", index=2, frame=frame)
            keyframe_counter += 2

        core_scale = 0.78 + 0.33 * full + 0.20 * transient
        core.scale = (core_scale, core_scale, core_scale)
        core.rotation_euler[2] = frame * 0.018 + high * 0.35
        core.keyframe_insert(data_path="scale", frame=frame)
        core.keyframe_insert(data_path="rotation_euler", index=2, frame=frame)
        keyframe_counter += 4

        band_values = (low, mid, high)
        for j, ring in enumerate(rings):
            band = band_values[j]
            s = 1.0 + 0.11 * band + 0.035 * transient
            ring.scale = (s, s, s)
            ring.rotation_euler[0] = 0.15 * math.sin(frame * 0.012 + j)
            ring.rotation_euler[1] = 0.15 * math.cos(frame * 0.010 + j)
            ring.rotation_euler[2] = frame * (0.004 + j * 0.002) * (1.0 + 0.35 * band)
            ring.keyframe_insert(data_path="scale", frame=frame)
            ring.keyframe_insert(data_path="rotation_euler", frame=frame)
            keyframe_counter += 6

        lights[0].data.energy = 540 + 920 * low + 620 * transient
        lights[1].data.energy = 420 + 780 * mid
        lights[2].data.energy = 460 + 980 * high + 450 * transient
        for light in lights:
            light.data.keyframe_insert(data_path="energy", frame=frame)
            keyframe_counter += 1

        theta = frame * 0.0065 + 0.10 * math.sin(frame * 0.021)
        radius = 8.2 - 0.65 * full - 0.25 * transient
        camera.location = (
            radius * math.cos(theta),
            radius * math.sin(theta),
            3.9 + 0.65 * mid + 0.25 * transient,
        )
        look_at(camera, (0, 0, 1.15 + 0.22 * low))
        camera.keyframe_insert(data_path="location", frame=frame)
        camera.keyframe_insert(data_path="rotation_euler", frame=frame)
        keyframe_counter += 6

    for obj in [*bars, core, *rings, camera]:
        linearize(obj)
    for light in lights:
        if light.data.animation_data and light.data.animation_data.action:
            for fcurve in light.data.animation_data.action.fcurves:
                for point in fcurve.keyframe_points:
                    point.interpolation = "LINEAR"

    return {
        "animated_objects": len(bars) + 1 + len(rings) + len(lights) + 1,
        "bar_count": len(bars),
        "keyframe_insert_calls": keyframe_counter,
    }


def build_scene() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not ANALYSIS_PATH.is_file():
        raise RuntimeError(f"audio analysis missing: {ANALYSIS_PATH}")

    analysis = json.loads(ANALYSIS_PATH.read_text(encoding="utf-8"))
    frames = analysis.get("frames") or []
    meta = analysis.get("analysis") or {}
    if len(frames) != FRAME_END:
        raise RuntimeError(f"expected {FRAME_END} analysis frames, got {len(frames)}")
    if int(meta.get("fps", 0)) != FPS:
        raise RuntimeError(f"analysis fps mismatch: {meta.get('fps')}")

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
    if bg:
        bg.inputs["Color"].default_value = (0.004, 0.006, 0.014, 1)
        bg.inputs["Strength"].default_value = 0.09

    floor_mat = material("Floor", (0.022, 0.030, 0.045), 0.45, 0.32)
    low_mat = material("Low", (0.86, 0.18, 0.06), 0.42, 0.24)
    mid_mat = material("Mid", (0.03, 0.62, 0.82), 0.36, 0.22)
    high_mat = material("High", (0.62, 0.16, 0.92), 0.38, 0.20)
    core_mat = material("Core", (0.86, 0.92, 1.00), 0.72, 0.13)

    bpy.ops.mesh.primitive_plane_add(size=18.0, location=(0, 0, 0))
    floor = bpy.context.object
    floor.name = "StageFloor"
    floor.data.materials.append(floor_mat)

    bars = []
    bar_mats = (low_mat, mid_mat, high_mat)
    for i in range(BAR_COUNT):
        bars.append(add_bar(i, 3.15, bar_mats[i % 3]))

    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.0, location=(0, 0, 1.18))
    core = bpy.context.object
    core.name = "TransientCore"
    core.data.materials.append(core_mat)

    rings = [
        add_ring("LowRing", 1.55, 0.055, 1.15, low_mat),
        add_ring("MidRing", 1.95, 0.045, 1.15, mid_mat),
        add_ring("HighRing", 2.35, 0.035, 1.15, high_mat),
    ]

    camera_data = bpy.data.cameras.new("Camera")
    camera = bpy.data.objects.new("Camera", camera_data)
    bpy.context.collection.objects.link(camera)
    scene.camera = camera
    camera_data.lens = 52.0

    lights = [
        add_area_light("LowLight", (-4.5, -4.0, 5.8), (1.0, 0.24, 0.08), 850, 3.6),
        add_area_light("MidLight", (4.2, -2.2, 5.2), (0.10, 0.72, 1.0), 700, 3.2),
        add_area_light("HighLight", (0.5, 4.6, 6.3), (0.65, 0.18, 1.0), 760, 3.0),
    ]

    animation = animate_scene(scene, frames, bars, core, rings, lights, camera)

    scene.frame_set(FRAME_START)
    bpy.context.view_layer.update()

    report = {
        "experiment": EXPERIMENT,
        "engine": engine,
        "render_samples": samples,
        "frame_start": FRAME_START,
        "frame_end": FRAME_END,
        "fps": FPS,
        "duration_seconds": FRAME_END / FPS,
        "resolution": [RES_X, RES_Y],
        "audio": {
            "source": analysis.get("source"),
            "source_size_bytes": analysis.get("source_size_bytes"),
            "source_sha256": analysis.get("source_sha256"),
            "analysis_fps": meta.get("fps"),
            "analysis_sample_rate": meta.get("sample_rate"),
            "analysis_frame_count": meta.get("frame_count"),
            "band_filters": meta.get("band_filters"),
            "beat_frames": meta.get("beat_frames"),
            "beat_count": meta.get("beat_count"),
            "mean_full": meta.get("mean_full"),
            "max_full": meta.get("max_full"),
            "mean_transient": meta.get("mean_transient"),
            "max_transient": meta.get("max_transient"),
        },
        "visual": animation,
        "sync_mapping": {
            "low": "every third radial bar + warm area light + target height",
            "mid": "every third radial bar + cyan area light + camera height",
            "high": "every third radial bar + violet area light + ring spin",
            "full": "core scale + camera radius",
            "transient": "core pulse + bar accent + light accent + camera punch-in",
        },
        "blend": BLEND_PATH.name,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))

    print(f"BLENDER_ENGINE={engine}")
    print(f"AUDIO_SOURCE={analysis.get('source')}")
    print(f"AUDIO_BEATS={meta.get('beat_count')}")
    print(f"ANIMATED_OBJECTS={animation['animated_objects']}")
    print(f"KEYFRAME_INSERT_CALLS={animation['keyframe_insert_calls']}")
    print(f"BLEND_PATH={BLEND_PATH}")


if __name__ == "__main__":
    build_scene()
