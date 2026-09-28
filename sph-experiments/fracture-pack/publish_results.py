from __future__ import annotations
import argparse, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main():
    p = argparse.ArgumentParser()
    p.add_argument("artifacts", type=Path)
    p.add_argument("results", type=Path)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--run-number", required=True)
    p.add_argument("--run-id", required=True)
    a = p.parse_args()
    cfg = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))

    for case, spec in cfg["cases"].items():
        name = f"sph-fracture-{case}"
        src = a.artifacts / name
        dst = a.results / name
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True)
        for fn in ("validation.json", "preview.png", "media.mp4", "case-metadata.json"):
            s = src / fn
            if not s.is_file() or s.stat().st_size == 0:
                raise SystemExit(f"missing {s}")
            shutil.copy2(s, dst / fn)

        validation = json.loads((src / "validation.json").read_text())
        pages = {
            "title": f"True fracture SPH — {spec['title']}",
            "description": f"{spec['description']} Phase-field fracture via SoliDualSPHysics; Gc={spec['Gc']}, impact velocity={spec['maxv']} m/s. Exploratory, not a validation reproduction.",
            "source_path": "sph-experiments/fracture-pack",
            "preview": "preview.png",
            "media": "media.mp4",
            "validation": "validation.json",
            "source_commit": a.source_commit,
            "run_number": a.run_number,
            "run_id": a.run_id
        }
        (dst / "pages.json").write_text(json.dumps(pages, indent=2) + "\n")
        (dst / "README.md").write_text(
            f"# {pages['title']}\n\n"
            f"- phase-field fracture: enabled\n"
            f"- Gc: {spec['Gc']} J/m^2\n"
            f"- imposed impact velocity: {spec['maxv']} m/s\n"
            f"- VTK frames: {validation['vtk_files']}\n"
            f"- fracture scalar candidate: {validation.get('fracture_scalar_candidate')}\n"
            f"- upstream: naqibr/SoliDualSPHysics, Kalthoff-Winkler example\n"
            f"- source commit: `{a.source_commit}`\n"
            f"- Actions run: `{a.run_number}` (`{a.run_id}`)\n"
        )
        print(f"published {name}")

if __name__ == "__main__":
    main()
