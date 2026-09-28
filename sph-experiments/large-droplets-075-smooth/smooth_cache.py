from __future__ import annotations

import argparse
import json
import math
import shutil
import time
from pathlib import Path

import numpy as np


ITERATIONS = 5
LAMBDA = 0.45
MU = -0.47


def unique_undirected_edges(triangles: np.ndarray) -> np.ndarray:
    edges = np.concatenate(
        (
            triangles[:, [0, 1]],
            triangles[:, [1, 2]],
            triangles[:, [2, 0]],
        ),
        axis=0,
    )
    edges = np.sort(edges.astype(np.int32, copy=False), axis=1)
    return np.unique(edges, axis=0)


def laplacian_step(
    vertices: np.ndarray,
    edges: np.ndarray,
    weight: float,
) -> np.ndarray:
    n = len(vertices)
    sums = np.zeros((n, 3), dtype=np.float64)
    counts = np.zeros(n, dtype=np.int32)

    a = edges[:, 0]
    b = edges[:, 1]
    np.add.at(sums, a, vertices[b])
    np.add.at(sums, b, vertices[a])
    np.add.at(counts, a, 1)
    np.add.at(counts, b, 1)

    out = vertices.astype(np.float64, copy=True)
    mask = counts > 0
    mean = sums[mask] / counts[mask, None]
    out[mask] += weight * (mean - out[mask])
    return out.astype(np.float32)


def taubin_smooth(vertices: np.ndarray, triangles: np.ndarray) -> tuple[np.ndarray, int]:
    edges = unique_undirected_edges(triangles)
    result = vertices.astype(np.float32, copy=True)
    for _ in range(ITERATIONS):
        result = laplacian_step(result, edges, LAMBDA)
        result = laplacian_step(result, edges, MU)
    return result, len(edges)


def bbox(vertices: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return vertices.min(axis=0), vertices.max(axis=0)


def bbox_volume(vmin: np.ndarray, vmax: np.ndarray) -> float:
    extent = np.maximum(vmax - vmin, 0.0)
    return float(np.prod(extent))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_cache", type=Path)
    parser.add_argument("output_cache", type=Path)
    args = parser.parse_args()

    source_manifest = json.loads(
        (args.input_cache / "manifest.json").read_text(encoding="utf-8")
    )
    if source_manifest.get("particle_radius") != 0.075:
        raise SystemExit(
            f"expected radius-0.075 source cache, got {source_manifest.get('particle_radius')}"
        )
    if int(source_manifest.get("frames", 0)) != 61:
        raise SystemExit(f"expected 61 frames, got {source_manifest.get('frames')}")

    out_surfaces = args.output_cache / "surfaces"
    out_surfaces.mkdir(parents=True, exist_ok=True)

    frames = []
    total_bytes = 0
    total_seconds = 0.0
    mean_displacements = []
    max_displacements = []
    bbox_volume_ratios = []

    for record in source_manifest["surface_frames"]:
        src = args.input_cache / "surfaces" / record["npz"]
        data = np.load(src)
        vertices = np.asarray(data["vertices"], dtype=np.float32)
        triangles = np.asarray(data["triangles"], dtype=np.int32)

        raw_min, raw_max = bbox(vertices)
        raw_center = vertices.mean(axis=0)
        raw_volume = bbox_volume(raw_min, raw_max)

        t0 = time.perf_counter()
        smoothed, edge_count = taubin_smooth(vertices, triangles)
        seconds = time.perf_counter() - t0
        total_seconds += seconds

        smooth_min, smooth_max = bbox(smoothed)
        smooth_center = smoothed.mean(axis=0)
        smooth_volume = bbox_volume(smooth_min, smooth_max)

        delta = np.linalg.norm(
            smoothed.astype(np.float64) - vertices.astype(np.float64),
            axis=1,
        )
        mean_disp = float(np.mean(delta))
        max_disp = float(np.max(delta))
        volume_ratio = smooth_volume / raw_volume if raw_volume > 0 else 1.0

        mean_displacements.append(mean_disp)
        max_displacements.append(max_disp)
        bbox_volume_ratios.append(volume_ratio)

        out_name = record["npz"]
        out = out_surfaces / out_name
        np.savez_compressed(out, vertices=smoothed, triangles=triangles)
        total_bytes += out.stat().st_size

        updated = dict(record)
        updated.update(
            {
                "npz_bytes": out.stat().st_size,
                "smoothing_seconds": seconds,
                "edge_count": edge_count,
                "raw_bbox_min": [float(v) for v in raw_min],
                "raw_bbox_max": [float(v) for v in raw_max],
                "smooth_bbox_min": [float(v) for v in smooth_min],
                "smooth_bbox_max": [float(v) for v in smooth_max],
                "raw_centroid": [float(v) for v in raw_center],
                "smooth_centroid": [float(v) for v in smooth_center],
                "mean_vertex_displacement": mean_disp,
                "max_vertex_displacement": max_disp,
                "bbox_volume_ratio": volume_ratio,
            }
        )
        frames.append(updated)
        print(
            f"SMOOTH frame={record['sequence_frame']}/61 "
            f"vertices={len(vertices)} faces={len(triangles)} edges={edge_count} "
            f"mean_disp={mean_disp:.6f} max_disp={max_disp:.6f} "
            f"bbox_ratio={volume_ratio:.6f} seconds={seconds:.3f}"
        )

    manifest = dict(source_manifest)
    manifest["visual_variant"] = "large-droplets-075-taubin5"
    manifest["smoothing"] = {
        "method": "taubin",
        "iterations": ITERATIONS,
        "lambda": LAMBDA,
        "mu": MU,
        "topology_preserved": True,
    }
    manifest["surface_frames"] = frames
    manifest["surface_npz_total_bytes"] = total_bytes
    manifest["mesh_smoothing_total_seconds"] = total_seconds
    manifest["mesh_smoothing_metrics"] = {
        "mean_vertex_displacement_average": float(np.mean(mean_displacements)),
        "mean_vertex_displacement_max_frame": float(np.max(mean_displacements)),
        "max_vertex_displacement_global": float(np.max(max_displacements)),
        "bbox_volume_ratio_average": float(np.mean(bbox_volume_ratios)),
        "bbox_volume_ratio_min": float(np.min(bbox_volume_ratios)),
        "bbox_volume_ratio_max": float(np.max(bbox_volume_ratios)),
    }

    # Keep the original reconstruction time separately; no SPH or pySplashSurf
    # work was rerun for this variant.
    manifest["source_reconstruction_total_seconds"] = source_manifest.get(
        "reconstruction_total_seconds"
    )
    manifest["reconstruction_total_seconds"] = 0.0

    (args.output_cache / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "frames": manifest["frames"],
                "smoothing": manifest["smoothing"],
                "surface_npz_total_bytes": total_bytes,
                "mesh_smoothing_total_seconds": total_seconds,
                "metrics": manifest["mesh_smoothing_metrics"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
