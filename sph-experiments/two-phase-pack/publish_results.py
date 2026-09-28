from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifacts", type=Path)
    parser.add_argument("results", type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--run-number", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    config = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    for case, spec in config["cases"].items():
        name = f"sph-two-phase-{case}"
        src = args.artifacts / name
        dst = args.results / name
        if not src.is_dir():
            raise SystemExit(f"missing artifact directory: {src}")

        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True)

        expected = [
            "validation.json",
            "preview.png",
            "media.mp4",
            f"{name}.blend",
            "two-phase-points.usdc",
        ]
        for filename in expected:
            source = src / filename
            if not source.is_file() or source.stat().st_size == 0:
                raise SystemExit(f"missing output: {source}")
            shutil.copy2(source, dst / filename)

        manifest_src = src / "points" / "manifest.json"
        if not manifest_src.is_file():
            raise SystemExit(f"missing point manifest: {manifest_src}")
        shutil.copy2(manifest_src, dst / "manifest.json")

        a = spec["materials"]["PhaseA"]
        b = spec["materials"]["PhaseB"]
        pages = {
            "title": f"SPH Two-phase — {spec['title']}",
            "description": (
                f"{spec['description']} "
                f"PhaseA rho={a['density']}, viscosity={a['viscosity']}; "
                f"PhaseB rho={b['density']}, viscosity={b['viscosity']}."
            ),
            "source_path": "sph-experiments/two-phase-pack",
            "preview": "preview.png",
            "media": "media.mp4",
            "validation": "validation.json",
            "source_commit": args.source_commit,
            "run_number": args.run_number,
            "run_id": args.run_id,
        }
        (dst / "pages.json").write_text(
            json.dumps(pages, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (dst / "README.md").write_text(
            f"# {pages['title']}\n\n"
            f"- source commit: `{args.source_commit}`\n"
            f"- Actions run: `{args.run_number}` (`{args.run_id}`)\n"
            f"- PhaseA: density={a['density']}, viscosity={a['viscosity']}\n"
            f"- PhaseB: density={b['density']}, viscosity={b['viscosity']}\n"
            f"- representation: two SPlisHSPlasH fluid models -> separate VTK -> NPZ -> USD -> Blender Geometry Nodes\n"
            f"- Blender: `{name}.blend`\n"
            f"- point cache: `two-phase-points.usdc`\n",
            encoding="utf-8",
        )
        print(f"published {name}")

if __name__ == "__main__":
    main()
