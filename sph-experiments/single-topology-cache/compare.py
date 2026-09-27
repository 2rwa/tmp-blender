from __future__ import annotations

import json
from pathlib import Path


ROOT = Path.cwd()
OUT = ROOT / "output" / "sph-single-topology-cache"
BASELINE = ROOT / "results" / "sph-cache-format-compare" / "comparison.json"

exports = json.loads((OUT / "export-metrics.json").read_text(encoding="utf-8"))
abc = json.loads((OUT / "alembic-validation.json").read_text(encoding="utf-8"))
usd = json.loads((OUT / "usd-validation.json").read_text(encoding="utf-8"))
container_baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

payload = {
    "source_blend_bytes": exports["source_blend_bytes"],
    "single_object": {
        "alembic": {
            "cache_bytes": exports["alembic"]["bytes"],
            "export_seconds": exports["alembic"]["export_seconds"],
            "import_seconds": abc["import_seconds"],
            "scrub_13_frames_seconds": abc["scrub_13_frames_seconds"],
            "mesh_objects": abc["mesh_objects"],
            "imported_blend_bytes": abc["imported_blend_bytes"],
            "replay_errors": len(abc["errors"]),
            "modifiers": abc["modifiers"],
        },
        "usd": {
            "cache_bytes": exports["usd"]["bytes"],
            "export_seconds": exports["usd"]["export_seconds"],
            "import_seconds": usd["import_seconds"],
            "scrub_13_frames_seconds": usd["scrub_13_frames_seconds"],
            "mesh_objects": usd["mesh_objects"],
            "imported_blend_bytes": usd["imported_blend_bytes"],
            "replay_errors": len(usd["errors"]),
            "modifiers": usd["modifiers"],
        },
    },
    "thirteen_object_container_baseline": container_baseline["formats"],
}

for fmt in ("alembic", "usd"):
    single = payload["single_object"][fmt]
    prior = payload["thirteen_object_container_baseline"][fmt]
    single["size_vs_13_object_cache_ratio"] = (
        single["cache_bytes"] / prior["cache_bytes"]
    )

(OUT / "comparison.json").write_text(
    json.dumps(payload, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(payload, indent=2))

for fmt in ("alembic", "usd"):
    entry = payload["single_object"][fmt]
    if entry["mesh_objects"] != 1 or entry["replay_errors"]:
        raise SystemExit(f"{fmt} did not preserve single-object varying topology")
