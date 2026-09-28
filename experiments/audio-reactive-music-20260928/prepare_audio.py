from __future__ import annotations

import hashlib
import json
import math
import statistics
import subprocess
import sys
from array import array
from pathlib import Path

ROOT = Path.cwd()
SOURCE = ROOT / "assets" / "music" / "20260928_000.mp3"
OUTPUT_DIR = ROOT / "output"
OUTPUT = OUTPUT_DIR / "music-sync-analysis.json"

FPS = 24
DURATION_SECONDS = 20.0
SAMPLE_RATE = 8000
FRAME_COUNT = int(FPS * DURATION_SECONDS)

FILTERS = {
    "full": None,
    "low": "lowpass=f=180",
    "mid": "highpass=f=180,lowpass=f=2500",
    "high": "highpass=f=2500",
}


def ffprobe() -> dict:
    raw = subprocess.check_output(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration:stream=index,codec_type,codec_name,sample_rate,channels",
            "-of", "json",
            str(SOURCE),
        ],
        text=True,
    )
    return json.loads(raw)


def decode(filter_spec: str | None) -> list[int]:
    cmd = [
        "ffmpeg", "-v", "error", "-nostdin",
        "-i", str(SOURCE),
        "-t", f"{DURATION_SECONDS:.3f}",
        "-map", "0:a:0",
        "-ac", "1",
        "-ar", str(SAMPLE_RATE),
    ]
    if filter_spec:
        cmd += ["-af", filter_spec]
    cmd += ["-f", "s16le", "-acodec", "pcm_s16le", "pipe:1"]
    raw = subprocess.check_output(cmd)
    samples = array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    return list(samples)


def frame_rms(samples: list[int]) -> list[float]:
    values = []
    for i in range(FRAME_COUNT):
        start = round(i * SAMPLE_RATE / FPS)
        end = round((i + 1) * SAMPLE_RATE / FPS)
        chunk = samples[start:end]
        if not chunk:
            values.append(0.0)
            continue
        mean_square = sum(float(v) * float(v) for v in chunk) / len(chunk)
        values.append(math.sqrt(mean_square) / 32768.0)
    return values


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 1.0
    idx = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * p)))
    return max(ordered[idx], 1e-9)


def normalize(values: list[float]) -> tuple[list[float], float]:
    ref = percentile(values, 0.95)
    out = [min(1.35, math.sqrt(max(0.0, v) / ref)) for v in values]
    return out, ref


def moving_average(values: list[float], radius: int = 1) -> list[float]:
    out = []
    for i in range(len(values)):
        lo = max(0, i - radius)
        hi = min(len(values), i + radius + 1)
        out.append(sum(values[lo:hi]) / (hi - lo))
    return out


def main() -> None:
    if not SOURCE.is_file():
        raise SystemExit(f"music source missing: {SOURCE}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    probe = ffprobe()
    format_duration = float((probe.get("format") or {}).get("duration") or 0.0)
    if format_duration < DURATION_SECONDS - 0.25:
        raise SystemExit(
            f"music is shorter than requested sample: duration={format_duration:.3f}s "
            f"requested={DURATION_SECONDS:.3f}s"
        )

    normalized: dict[str, list[float]] = {}
    references: dict[str, float] = {}

    for name, filter_spec in FILTERS.items():
        samples = decode(filter_spec)
        if len(samples) < int(SAMPLE_RATE * (DURATION_SECONDS - 0.25)):
            raise SystemExit(f"decoded audio too short for band {name}: {len(samples)} samples")
        raw_values = frame_rms(samples)
        normalized_values, ref = normalize(raw_values)
        normalized[name] = moving_average(normalized_values, radius=1)
        references[name] = ref

    full = normalized["full"]
    raw_delta = [0.0]
    for i in range(1, FRAME_COUNT):
        baseline = 0.72 * full[i - 1] + 0.28 * (full[i - 2] if i > 1 else full[i - 1])
        raw_delta.append(max(0.0, full[i] - baseline))
    transient_ref = percentile(raw_delta, 0.97)
    transient = [min(1.5, v / transient_ref) for v in raw_delta]

    beat_frames = []
    last = -999
    for i, value in enumerate(transient):
        frame = i + 1
        if value >= 0.72 and frame - last >= 5:
            beat_frames.append(frame)
            last = frame

    frames = []
    for i in range(FRAME_COUNT):
        frames.append(
            {
                "frame": i + 1,
                "full": round(full[i], 6),
                "low": round(normalized["low"][i], 6),
                "mid": round(normalized["mid"][i], 6),
                "high": round(normalized["high"][i], 6),
                "transient": round(transient[i], 6),
            }
        )

    source_bytes = SOURCE.read_bytes()
    result = {
        "source": str(SOURCE.relative_to(ROOT)),
        "source_size_bytes": len(source_bytes),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "probe": probe,
        "analysis": {
            "fps": FPS,
            "duration_seconds": DURATION_SECONDS,
            "sample_rate": SAMPLE_RATE,
            "frame_count": FRAME_COUNT,
            "band_filters": FILTERS,
            "normalization_reference_rms": {
                key: round(value, 8) for key, value in references.items()
            },
            "transient_reference": round(transient_ref, 8),
            "beat_frames": beat_frames,
            "beat_count": len(beat_frames),
            "mean_full": round(statistics.fmean(full), 6),
            "max_full": round(max(full), 6),
            "mean_transient": round(statistics.fmean(transient), 6),
            "max_transient": round(max(transient), 6),
        },
        "frames": frames,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["analysis"], indent=2))
    print(f"AUDIO_ANALYSIS={OUTPUT}")
    print(f"AUDIO_SHA256={result['source_sha256']}")


if __name__ == "__main__":
    main()
