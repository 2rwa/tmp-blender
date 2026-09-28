from __future__ import annotations

import json
from pathlib import Path

ROOT = Path.cwd()
BASELINE = json.loads(
    (ROOT / "results" / "sph-long-duration-5s" / "validation.json").read_text(
        encoding="utf-8"
    )
)
LARGE = json.loads(
    (ROOT / "results" / "sph-large-droplets-075" / "validation.json").read_text(
        encoding="utf-8"
    )
)
SMOOTH = json.loads(
    (ROOT / "output" / "sph-large-droplets-075-smooth" / "validation.json").read_text(
        encoding="utf-8"
    )
)

def compact(d):
    return {
        "particle_radius": d.get("particle_radius", 0.05),
        "surface_vertices_min": d["surface_vertices_min"],
        "surface_vertices_max": d["surface_vertices_max"],
        "surface_faces_min": d["surface_faces_min"],
        "surface_faces_max": d["surface_faces_max"],
        "surface_npz_total_bytes": d["surface_npz_total_bytes"],
        "usd_bytes": d["usd_bytes"],
        "blend_bytes": d["blend_bytes"],
        "render_seconds": d["render_seconds"],
    }

payload = {
    "baseline_radius_005": compact(BASELINE),
    "large_droplets_radius_0075": compact(LARGE),
    "large_droplets_radius_0075_taubin5": compact(SMOOTH),
    "smoothing": SMOOTH.get("mesh_smoothing"),
    "smoothing_total_seconds": SMOOTH.get("mesh_smoothing_total_seconds"),
    "smoothing_metrics": SMOOTH.get("mesh_smoothing_metrics"),
}
payload["smooth_vs_unsmoothed"] = {
    "npz_bytes_ratio": SMOOTH["surface_npz_total_bytes"] / LARGE["surface_npz_total_bytes"],
    "usd_bytes_ratio": SMOOTH["usd_bytes"] / LARGE["usd_bytes"],
    "blend_bytes_ratio": SMOOTH["blend_bytes"] / LARGE["blend_bytes"],
    "render_seconds_ratio": SMOOTH["render_seconds"] / LARGE["render_seconds"],
    "vertices_same_range": (
        SMOOTH["surface_vertices_min"] == LARGE["surface_vertices_min"]
        and SMOOTH["surface_vertices_max"] == LARGE["surface_vertices_max"]
    ),
    "faces_same_range": (
        SMOOTH["surface_faces_min"] == LARGE["surface_faces_min"]
        and SMOOTH["surface_faces_max"] == LARGE["surface_faces_max"]
    ),
}

out = ROOT / "output" / "sph-large-droplets-075-smooth" / "comparison.json"
out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2))
