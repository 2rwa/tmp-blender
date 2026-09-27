from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageStat

EXPERIMENT = "character-room-interior-eevee"
FRAME_END = 360
FPS = 24


def validate_preview(path):
    if not path.exists():
        raise SystemExit(f"preview missing: {path}")
    if path.stat().st_size < 12000:
        raise SystemExit(f"preview suspiciously small: {path.stat().st_size}")
    with Image.open(path) as image:
        image.load()
        if image.size != (480, 360):
            raise SystemExit(f"unexpected preview size: {image.size}")
        gray = image.convert("L")
        stat = ImageStat.Stat(gray)
        extrema = gray.getextrema()
        stddev = float(stat.stddev[0])
        if extrema[1] - extrema[0] < 55:
            raise SystemExit(f"insufficient luminance range: {extrema}")
        if stddev < 12.0:
            raise SystemExit(f"preview too uniform: {stddev:.2f}")
    return {
        "size_bytes": path.stat().st_size,
        "luminance_min": extrema[0],
        "luminance_max": extrema[1],
        "luminance_stddev": round(stddev, 3),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def validate_video(path):
    if not path.exists():
        raise SystemExit(f"video missing: {path}")
    if path.stat().st_size < 50000:
        raise SystemExit(f"room-tour video suspiciously small: {path.stat().st_size}")
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height,avg_frame_rate,nb_frames",
            "-show_entries", "format=size,duration",
            "-of", "json", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(proc.stdout)
    stream = (data.get("streams") or [{}])[0]
    fmt = data.get("format") or {}
    width = int(stream.get("width", 0))
    height = int(stream.get("height", 0))
    duration = float(fmt.get("duration") or 0.0)
    frames = int(stream.get("nb_frames") or 0)
    if (width, height) != (480, 360):
        raise SystemExit(f"unexpected movie dimensions: {(width, height)}")
    if not (14.5 <= duration <= 15.5):
        raise SystemExit(f"unexpected movie duration: {duration}")
    if frames and frames != FRAME_END:
        raise SystemExit(f"unexpected encoded frame count: {frames}")
    return {
        "size_bytes": path.stat().st_size,
        "duration_seconds": round(duration, 3),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "nb_frames": stream.get("nb_frames"),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def validate_report(report_path, blend_path):
    if not report_path.exists():
        raise SystemExit(f"report missing: {report_path}")
    if not blend_path.exists():
        raise SystemExit(f"blend missing: {blend_path}")
    if blend_path.stat().st_size < 1_000_000:
        raise SystemExit(f"blend suspiciously small: {blend_path.stat().st_size}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("experiment") != EXPERIMENT:
        raise SystemExit("experiment id mismatch")
    if report.get("frame_end") != FRAME_END or report.get("fps") != FPS:
        raise SystemExit("unexpected timeline")

    room = report.get("room") or {}
    dims = (
        float(room.get("width_m", 0)),
        float(room.get("depth_m", 0)),
        float(room.get("height_m", 0)),
    )
    if dims != (7.2, 5.4, 3.0):
        raise SystemExit(f"unexpected room dimensions: {dims}")
    if room.get("open_front") is not True:
        raise SystemExit("room should use an open-front presentation layout")
    if int(room.get("room_mesh_count", 0)) < 8:
        raise SystemExit("room shell is incomplete")
    if int(room.get("furniture_object_count", 0)) < 25:
        raise SystemExit("not enough furniture geometry")
    if len(room.get("furniture_groups") or []) < 7:
        raise SystemExit("furniture groups missing")
    if int(room.get("decor_object_count", 0)) < 8:
        raise SystemExit("decor/window geometry missing")
    if int(room.get("light_count", 0)) < 4:
        raise SystemExit("room lighting setup incomplete")
    if int(room.get("camera_keyframes", 0)) != 4:
        raise SystemExit("camera tour keyframes missing")
    if int(room.get("total_scene_mesh_count", 0)) < 45:
        raise SystemExit("scene mesh count too low")

    source = report.get("source") or {}
    if source.get("publisher") != "Quaternius" or source.get("license") != "CC0 1.0":
        raise SystemExit("character source provenance missing")

    char = report.get("character") or {}
    if int(char.get("mesh_count", 0)) < 1:
        raise SystemExit("no character mesh")
    if int(char.get("armature_count", 0)) < 1:
        raise SystemExit("no character armature")
    if int(char.get("action_count", 0)) < 13:
        raise SystemExit("expected the known 13-action Warrior asset")
    if "idle" not in str(char.get("selected_action", "")).lower():
        raise SystemExit(f"idle action not selected: {char.get('selected_action')}")
    height = float(char.get("preview_height_m", 0.0))
    if not (1.65 <= height <= 1.90):
        raise SystemExit(f"character scale is not room-realistic: {height}")

    return {
        "room_dimensions_m": dims,
        "room_mesh_count": room.get("room_mesh_count"),
        "furniture_object_count": room.get("furniture_object_count"),
        "decor_object_count": room.get("decor_object_count"),
        "furniture_groups": room.get("furniture_groups"),
        "light_count": room.get("light_count"),
        "camera_keyframes": room.get("camera_keyframes"),
        "total_scene_mesh_count": room.get("total_scene_mesh_count"),
        "character_height_m": height,
        "character_action_count": char.get("action_count"),
        "selected_action": char.get("selected_action"),
        "blend_size_bytes": blend_path.stat().st_size,
    }


def main():
    preview = Path(sys.argv[1] if len(sys.argv) > 1 else "output/preview.png")
    base = preview.parent
    result = {
        "video": f"{EXPERIMENT}.mp4",
        "preview": validate_preview(preview),
        "movie": validate_video(base / f"{EXPERIMENT}.mp4"),
        "report": validate_report(
            base / f"{EXPERIMENT}-report.json",
            base / f"{EXPERIMENT}.blend",
        ),
    }
    out = base / "validation.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
