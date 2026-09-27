from __future__ import annotations

import json
from pathlib import Path


ROOT = Path.cwd()
OUT = ROOT / "output" / "sph-cache-compare"

exports = json.loads((OUT / "export-metrics.json").read_text(encoding="utf-8"))
abc = json.loads((OUT / "alembic-validation.json").read_text(encoding="utf-8"))
usd = json.loads((OUT / "usd-validation.json").read_text(encoding="utf-8"))

source_bytes = int(exports["baseline"]["source_blend_bytes"])

formats = {}
for name, exp, val in (
    ("alembic", exports["alembic"], abc),
    ("usd", exports["usd"], usd),
):
    cache_bytes = int(exp["bytes"])
    formats[name] = {
        "cache_bytes": cache_bytes,
        "vs_source_blend_ratio": cache_bytes / source_bytes,
        "export_seconds": float(exp["export_seconds"]),
        "import_seconds": float(val["import_seconds"]),
        "scrub_13_frames_seconds": float(val["scrub_13_frames_seconds"]),
        "imported_blend_bytes": int(val["imported_blend_bytes"]),
        "mesh_objects": int(val["mesh_objects"]),
        "replay_errors": len(val["errors"]),
        "vertex_counts": [x.get("vertices") for x in val["observed"]],
        "face_counts": [x.get("faces") for x in val["observed"]],
    }

payload = {
    "baseline": exports["baseline"],
    "formats": formats,
}
(OUT / "comparison.json").write_text(
    json.dumps(payload, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(payload, indent=2))

for name, entry in formats.items():
    if entry["replay_errors"]:
        raise SystemExit(f"{name} replay errors: {entry['replay_errors']}")
