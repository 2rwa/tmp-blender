from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = ROOT / "experiments"
OUTPUT_DIR = ROOT / "output"
RESULTS_DIR = ROOT / "results"
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PAGE_MEDIA_MAX_BYTES = 5 * 1024 * 1024
REPO_BLEND_MAX_BYTES = 95 * 1024 * 1024


def experiment_dir(experiment_id: str) -> Path:
    if not SAFE_ID.fullmatch(experiment_id):
        raise SystemExit(f"invalid experiment id: {experiment_id!r}")
    path = EXPERIMENTS_DIR / experiment_id
    if not path.is_dir():
        raise SystemExit(f"experiment not found: {experiment_id}")
    return path


def load_manifest(experiment_id: str) -> dict:
    path = experiment_dir(experiment_id) / "experiment.json"
    if not path.is_file():
        raise SystemExit(f"manifest missing: {path.relative_to(ROOT)}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("id") != experiment_id:
        raise SystemExit(f"manifest id mismatch: expected {experiment_id!r}")
    if not data.get("preview_source"):
        raise SystemExit("manifest preview_source is required")
    return data


def all_experiments() -> list[str]:
    found = []
    if not EXPERIMENTS_DIR.exists():
        return found
    for path in sorted(EXPERIMENTS_DIR.iterdir()):
        if path.is_dir() and (path / "experiment.json").is_file() and SAFE_ID.fullmatch(path.name):
            found.append(path.name)
    return found


def git_changed_files(before: str, after: str) -> list[str]:
    zero = "0" * 40
    if not before or before == zero:
        return []
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", before, after],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def discover(args: argparse.Namespace) -> int:
    if args.manual:
        experiment_dir(args.manual)
        selected = [args.manual]
    else:
        known = set(all_experiments())
        changed = git_changed_files(args.before, args.after)
        selected_set: set[str] = set()
        common_changed = False

        for filename in changed:
            parts = Path(filename).parts
            if len(parts) >= 2 and parts[0] == "experiments" and parts[1] in known:
                selected_set.add(parts[1])
            if filename == ".github/workflows/blender-experiment.yml" or filename.startswith("tools/"):
                common_changed = True

        if not changed:
            if "orbital-sculpture" in known:
                selected_set.add("orbital-sculpture")
        elif common_changed and not selected_set:
            if "orbital-sculpture" in known:
                selected_set.add("orbital-sculpture")
            elif known:
                selected_set.add(sorted(known)[0])

        selected = sorted(selected_set)

    print("experiments=" + json.dumps(selected, separators=(",", ":")))
    return 0


def required_output_paths(experiment_id: str) -> list[Path]:
    manifest = load_manifest(experiment_id)
    names = ["validation.json", "blender-version.txt", manifest["preview_source"]]
    names.extend(manifest.get("required_outputs", []))
    unique = []
    seen = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        unique.append(OUTPUT_DIR / name)
    return unique


def check_render(experiment_id: str) -> int:
    manifest = load_manifest(experiment_id)
    names = ["blender-version.txt", manifest["preview_source"]]
    names.extend(manifest.get("required_outputs", []))

    missing = []
    empty = []
    seen = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        path = OUTPUT_DIR / name
        if not path.is_file():
            missing.append(str(path.relative_to(ROOT)))
        elif path.stat().st_size == 0:
            empty.append(str(path.relative_to(ROOT)))

    if missing or empty:
        if missing:
            print("missing render outputs:", ", ".join(missing))
        if empty:
            print("empty render outputs:", ", ".join(empty))
        return 1

    print(json.dumps({"experiment": experiment_id, "render_checkpoint": "ok"}, indent=2))
    return 0


def check(experiment_id: str) -> int:
    missing = []
    empty = []
    for path in required_output_paths(experiment_id):
        if not path.is_file():
            missing.append(str(path.relative_to(ROOT)))
        elif path.stat().st_size == 0:
            empty.append(str(path.relative_to(ROOT)))

    if missing or empty:
        if missing:
            print("missing outputs:", ", ".join(missing))
        if empty:
            print("empty outputs:", ", ".join(empty))
        return 1

    validation = json.loads((OUTPUT_DIR / "validation.json").read_text(encoding="utf-8"))
    print(json.dumps({"experiment": experiment_id, "validation": validation}, indent=2))
    return 0


def publish(args: argparse.Namespace) -> int:
    experiment_id = args.experiment
    if check(experiment_id) != 0:
        return 1

    manifest = load_manifest(experiment_id)
    destination = RESULTS_DIR / experiment_id
    destination.mkdir(parents=True, exist_ok=True)

    from PIL import Image

    preview_source = OUTPUT_DIR / manifest["preview_source"]
    with Image.open(preview_source) as image:
        image = image.convert("RGB")
        image.thumbnail((768, 768))
        image.save(destination / "preview.jpg", format="JPEG", quality=90, optimize=True)

    shutil.copy2(OUTPUT_DIR / "validation.json", destination / "validation.json")
    shutil.copy2(OUTPUT_DIR / "blender-version.txt", destination / "blender-version.txt")

    validation = json.loads((destination / "validation.json").read_text(encoding="utf-8"))

    media_destination = destination / "media.mp4"
    video_name = validation.get("video")
    if video_name:
        video_source = OUTPUT_DIR / str(video_name)
        if video_source.is_file() and video_source.stat().st_size <= PAGE_MEDIA_MAX_BYTES:
            shutil.copy2(video_source, media_destination)
            print(f"published page media: {media_destination.relative_to(ROOT)}")
        elif media_destination.exists():
            media_destination.unlink()
    elif media_destination.exists():
        media_destination.unlink()

    published_blends = []
    skipped_blends = []
    for blend_name in manifest.get("repo_blends", []):
        blend_source = OUTPUT_DIR / str(blend_name)
        blend_destination = destination / Path(str(blend_name)).name

        if not blend_source.is_file():
            raise SystemExit(f"repo blend missing: {blend_source}")

        size = blend_source.stat().st_size
        if size <= REPO_BLEND_MAX_BYTES:
            shutil.copy2(blend_source, blend_destination)
            published_blends.append((blend_destination.name, size))
            print(f"published repo blend: {blend_destination.relative_to(ROOT)} ({size} bytes)")
        else:
            if blend_destination.exists():
                blend_destination.unlink()
            skipped_blends.append((blend_destination.name, size))
            print(f"repo blend too large; artifact only: {blend_destination.name} ({size} bytes)")

    title = manifest.get("title", experiment_id)
    description = manifest.get("description", "")
    artifact_name = f"blender-{experiment_id}"

    lines = [f"# {title}", ""]
    if description:
        lines.extend([description, ""])
    lines.extend([
        f"- source commit: `{args.source_sha}`",
        f"- Actions run: `{args.run_number}` (`{args.run_id}`)",
        f"- full artifact: `{artifact_name}`",
        "",
    ])
    if published_blends or skipped_blends:
        lines.extend(["## Blend files", ""])
        for name, size in published_blends:
            lines.append(f"- Git: [{name}](./{name}) ({size:,} bytes)")
        for name, size in skipped_blends:
            lines.append(f"- Artifact only: `{name}` ({size:,} bytes; exceeds {REPO_BLEND_MAX_BYTES:,}-byte Git safety threshold)")
        lines.append("")

    lines.extend([
        "![Latest preview](./preview.jpg)",
        "",
        "## Validation",
        "",
        "```json",
        json.dumps(validation, indent=2, ensure_ascii=False),
        "```",
        "",
    ])
    (destination / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"published lightweight result to {destination.relative_to(ROOT)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="tmp-blender experiment helper")
    sub = parser.add_subparsers(dest="command", required=True)

    discover_parser = sub.add_parser("discover")
    discover_parser.add_argument("--manual", default="")
    discover_parser.add_argument("--before", default="")
    discover_parser.add_argument("--after", default="")

    render_check_parser = sub.add_parser("check-render")
    render_check_parser.add_argument("experiment")

    check_parser = sub.add_parser("check")
    check_parser.add_argument("experiment")

    publish_parser = sub.add_parser("publish")
    publish_parser.add_argument("experiment")
    publish_parser.add_argument("--source-sha", required=True)
    publish_parser.add_argument("--run-id", required=True)
    publish_parser.add_argument("--run-number", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "discover":
        return discover(args)
    if args.command == "check-render":
        return check_render(args.experiment)
    if args.command == "check":
        return check(args.experiment)
    if args.command == "publish":
        return publish(args)
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
