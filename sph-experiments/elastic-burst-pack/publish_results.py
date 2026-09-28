from __future__ import annotations
import argparse, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser()
    p.add_argument("artifacts",type=Path); p.add_argument("results",type=Path)
    p.add_argument("--source-commit",required=True); p.add_argument("--run-number",required=True); p.add_argument("--run-id",required=True)
    a=p.parse_args()
    cfg=json.loads((ROOT/"cases.json").read_text())
    for case,spec in cfg["cases"].items():
        name=f"sph-elastic-{case}"
        src=a.artifacts/name; dst=a.results/name
        if dst.exists(): shutil.rmtree(dst)
        dst.mkdir(parents=True)
        for fn in ("validation.json","preview.png","media.mp4",f"{name}.blend","elastic-points.usdc"):
            s=src/fn
            if not s.is_file() or s.stat().st_size == 0: raise SystemExit(f"missing {s}")
            shutil.copy2(s,dst/fn)
        mf=src/"points"/"manifest.json"
        if not mf.is_file(): raise SystemExit(f"missing {mf}")
        shutil.copy2(mf,dst/"manifest.json")
        e=spec["elasticity"]
        pages={
          "title":f"Elastic Burst SPH — {spec['title']}",
          "description":f"{spec['description']} Classification={spec['classification']}. Method={e['name']}, Young={e['youngsModulus']}.",
          "source_path":"sph-experiments/elastic-burst-pack","preview":"preview.png","media":"media.mp4","validation":"validation.json",
          "source_commit":a.source_commit,"run_number":a.run_number,"run_id":a.run_id
        }
        (dst/"pages.json").write_text(json.dumps(pages,indent=2)+"\n")
        (dst/"README.md").write_text(f"# {pages['title']}\n\n- classification: {spec['classification']}\n- source commit: `{a.source_commit}`\n- Actions run: `{a.run_number}` (`{a.run_id}`)\n")
        print(f"published {name}")

if __name__=="__main__":
    main()
