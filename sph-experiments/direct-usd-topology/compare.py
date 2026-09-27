from __future__ import annotations

import json
from pathlib import Path


ROOT = Path.cwd()
OUT = ROOT / "output" / "sph-single-topology-cache"

exported = json.loads((OUT / "direct-usd-export.json").read_text(encoding="utf-8"))
validated = json.loads((OUT / "direct-usd-validation.json").read_text(encoding="utf-8"))
baseline = json.loads(
    (ROOT / "results" / "sph-cache-format-compare" / "comparison.json").read_text(
        encoding="utf-8"
    )
)

prior_usd = baseline["formats"]["usd"]
payload = {
    "direct_single_mesh_usd": {
        "cache_bytes": exported["bytes"],
        "export_seconds": exported["export_seconds"],
        "import_seconds": validated["import_seconds"],
        "scrub_13_frames_seconds": validated["scrub_13_frames_seconds"],
        "mesh_objects": validated["mesh_objects"],
        "modifiers": validated["modifiers"],
        "replay_errors": len(validated["errors"]),
        "imported_blend_bytes": validated["imported_blend_bytes"],
        "time_sample_count": len(exported["points_time_samples"]),
    },
    "thirteen_object_usd_baseline": prior_usd,
}
payload["direct_single_mesh_usd"]["size_vs_13_object_usd_ratio"] = (
    payload["direct_single_mesh_usd"]["cache_bytes"] / prior_usd["cache_bytes"]
)

(OUT / "direct-usd-comparison.json").write_text(
    json.dumps(payload, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(payload, indent=2))

entry = payload["direct_single_mesh_usd"]
if entry["mesh_objects"] != 1:
    raise SystemExit("direct USD did not import as one mesh object")
if entry["replay_errors"]:
    raise SystemExit("direct USD replay has errors")
if entry["time_sample_count"] != 13:
    raise SystemExit("direct USD missing topology time samples")
