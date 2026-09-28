from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageStat

EXPERIMENT = "audio-reactive-music-20260928"
FRAME_END = 480
FPS = 24
EXPECTED_DURATION = FRAME_END / FPS
EXPECTED_SOURCE = "assets/music/20260928_000.mp3"


def validate_preview(path: Path) -> dict:
    if not path.is_file():
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
        if extrema[1] - extrema[0] < 50:
            raise SystemExit(f"insufficient luminance range: {extrema}")
        if stddev < 10.0:
            raise SystemExit(f"preview too uniform: {stddev:.2f}")
    return {
        "size_bytes": path.stat().st_size,
        "luminance_min": extrema[0],
        "luminance_max": extrema[1],
        "luminance_stddev": round(stddev, 3),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def probe_video(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"video missing: {path}")
    if path.stat().st_size < 80000:
        raise SystemExit(f"video suspiciously small: {path.stat().st_size}")
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries",
            "stream=index,codec_type,codec_name,width,height,avg_frame_rate,nb_frames,sample_rate,channels:"
            "format=size,duration",
            "-of", "json", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(proc.stdout)
    streams = data.get("streams") or []
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    if len(video_streams) != 1:
        raise SystemExit(f"expected one video stream, got {len(video_streams)}")
    if len(audio_streams) < 1:
        raise SystemExit("final MP4 has no audio stream")

    video = video_streams[0]
    audio = audio_streams[0]
    if (int(video.get("width", 0)), int(video.get("height", 0))) != (480, 360):
        raise SystemExit(f"unexpected movie dimensions: {video.get('width')}x{video.get('height')}")
    duration = float((data.get("format") or {}).get("duration") or 0.0)
    if not (EXPECTED_DURATION - 0.6 <= duration <= EXPECTED_DURATION + 0.6):
        raise SystemExit(f"unexpected movie duration: {duration}")
    frames = int(video.get("nb_frames") or 0)
    if frames and frames != FRAME_END:
        raise SystemExit(f"unexpected encoded frame count: {frames}")

    return {
        "size_bytes": path.stat().st_size,
        "duration_seconds": round(duration, 3),
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
        "audio_sample_rate": audio.get("sample_rate"),
        "audio_channels": audio.get("channels"),
        "avg_frame_rate": video.get("avg_frame_rate"),
        "nb_frames": video.get("nb_frames"),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def validate_report(report_path: Path, blend_path: Path) -> dict:
    if not report_path.is_file():
        raise SystemExit(f"report missing: {report_path}")
    if not blend_path.is_file():
        raise SystemExit(f"blend missing: {blend_path}")
    if blend_path.stat().st_size < 100000:
        raise SystemExit(f"blend suspiciously small: {blend_path.stat().st_size}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("experiment") != EXPERIMENT:
        raise SystemExit("experiment id mismatch")
    if report.get("frame_end") != FRAME_END or report.get("fps") != FPS:
        raise SystemExit("unexpected timeline")
    if report.get("resolution") != [480, 360]:
        raise SystemExit(f"unexpected resolution in report: {report.get('resolution')}")

    audio = report.get("audio") or {}
    if audio.get("source") != EXPECTED_SOURCE:
        raise SystemExit(f"wrong audio source: {audio.get('source')}")
    sha = str(audio.get("source_sha256") or "")
    if len(sha) != 64:
        raise SystemExit("source SHA-256 missing")
    if int(audio.get("analysis_frame_count") or 0) != FRAME_END:
        raise SystemExit("audio analysis frame count mismatch")
    if int(audio.get("analysis_fps") or 0) != FPS:
        raise SystemExit("audio analysis FPS mismatch")
    if float(audio.get("max_full") or 0.0) <= 0.2:
        raise SystemExit("audio RMS analysis looks empty")
    if float(audio.get("max_transient") or 0.0) <= 0.2:
        raise SystemExit("audio transient analysis looks empty")

    visual = report.get("visual") or {}
    if int(visual.get("bar_count") or 0) != 36:
        raise SystemExit("unexpected bar count")
    if int(visual.get("animated_objects") or 0) < 40:
        raise SystemExit("too few animated objects")
    if int(visual.get("keyframe_insert_calls") or 0) < 20000:
        raise SystemExit("too few animation keyframes")

    return {
        "source": audio.get("source"),
        "source_sha256": sha,
        "beat_count": audio.get("beat_count"),
        "max_full": audio.get("max_full"),
        "max_transient": audio.get("max_transient"),
        "animated_objects": visual.get("animated_objects"),
        "bar_count": visual.get("bar_count"),
        "keyframe_insert_calls": visual.get("keyframe_insert_calls"),
        "blend_size_bytes": blend_path.stat().st_size,
    }


def main() -> None:
    preview = Path(sys.argv[1] if len(sys.argv) > 1 else "output/preview.png")
    base = preview.parent
    video_path = base / f"{EXPERIMENT}.mp4"
    report_path = base / f"{EXPERIMENT}-report.json"
    blend_path = base / f"{EXPERIMENT}.blend"

    result = {
        "video": video_path.name,
        "preview": validate_preview(preview),
        "movie": probe_video(video_path),
        "report": validate_report(report_path, blend_path),
    }

    out = base / "validation.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
