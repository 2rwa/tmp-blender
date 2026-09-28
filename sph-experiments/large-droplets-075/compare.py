from __future__ import annotations

import json
from pathlib import Path

ROOT = Path.cwd()
BASELINE = json.loads(
    (ROOT / "results" / "sph-long-duration-5s" / "validation.json").read_text(
        encoding="utf-8"
    )
)
VARIANT = json.loads(
    (ROOT / "output" / "sph-large-droplets-075" / "validation.json").read_text(
        encoding="utf-8"
    )
)

payload = {
    "baseline": {
        "particle_radius": 0.05,
        "surface_vertices_min": BASELINE["surface_vertices_min"],
        "surface_vertices_max": BASELINE["surface_vertices_max"],
        "surface_faces_min": BASELINE["surface_faces_min"],
        "surface_faces_max": BASELINE["surface_faces_max"],
        "surface_npz_total_bytes": BASELINE["surface_npz_total_bytes"],
        "usd_bytes": BASELINE["usd_bytes"],
        "blend_bytes": BASELINE["blend_bytes"],
        "render_seconds": BASELINE["render_seconds"],
    },
    "large_droplets": {
        "particle_radius": VARIANT["particle_radius"],
        "surface_vertices_min": VARIANT["surface_vertices_min"],
        "surface_vertices_max": VARIANT["surface_vertices_max"],
        "surface_faces_min": VARIANT["surface_faces_min"],
        "surface_faces_max": VARIANT["surface_faces_max"],
        "surface_npz_total_bytes": VARIANT["surface_npz_total_bytes"],
        "usd_bytes": VARIANT["usd_bytes"],
        "blend_bytes": VARIANT["blend_bytes"],
        "render_seconds": VARIANT["render_seconds"],
    },
}
payload["ratios"] = {
    "radius": payload["large_droplets"]["particle_radius"] / payload["baseline"]["particle_radius"],
    "npz_bytes": payload["large_droplets"]["surface_npz_total_bytes"] / payload["baseline"]["surface_npz_total_bytes"],
    "usd_bytes": payload["large_droplets"]["usd_bytes"] / payload["baseline"]["usd_bytes"],
    "render_seconds": payload["large_droplets"]["render_seconds"] / payload["baseline"]["render_seconds"],
}

out = ROOT / "output" / "sph-large-droplets-075" / "comparison.json"
out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2))
