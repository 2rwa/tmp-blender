from __future__ import annotations
import argparse, json, math
from pathlib import Path
import meshio
import numpy as np

CANDIDATE_WORDS = ("phase", "fract", "damage", "crack", "pf")

def find_scalar(mesh):
    scored = []
    for key, value in mesh.point_data.items():
        arr = np.asarray(value)
        if arr.ndim > 1 and arr.shape[-1] == 1:
            arr = arr.reshape(-1)
        if arr.ndim != 1 or len(arr) != len(mesh.points):
            continue
        score = sum(w in key.lower() for w in CANDIDATE_WORDS)
        if score:
            scored.append((score, key, arr.astype(np.float64, copy=False)))
    if not scored:
        return None, None
    scored.sort(reverse=True)
    _, key, arr = scored[0]
    return key, arr

def main():
    p = argparse.ArgumentParser()
    p.add_argument("vtk_dir", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--case", required=True)
    p.add_argument("--max-render-frames", type=int, default=25)
    a = p.parse_args()

    files = sorted(a.vtk_dir.rglob("*.vtk"))
    if not files:
        raise SystemExit(f"no vtk files under {a.vtk_dir}")
    a.output.mkdir(parents=True, exist_ok=True)
    frame_dir = a.output / "frames"
    frame_dir.mkdir(exist_ok=True)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    stride = max(1, math.ceil(len(files) / a.max_render_frames))
    selected = files[::stride]
    if selected[-1] != files[-1]:
        selected.append(files[-1])

    stats = []
    all_fields = set()
    chosen_field = None
    global_scalar_min = None
    global_scalar_max = None
    particle_min = None
    particle_max = None

    for seq, path in enumerate(selected):
        mesh = meshio.read(path)
        pts = np.asarray(mesh.points, dtype=np.float64)
        if len(pts) == 0:
            continue
        all_fields.update(mesh.point_data.keys())
        particle_min = len(pts) if particle_min is None else min(particle_min, len(pts))
        particle_max = len(pts) if particle_max is None else max(particle_max, len(pts))
        key, scalar = find_scalar(mesh)
        if chosen_field is None and key is not None:
            chosen_field = key
        if chosen_field is not None and chosen_field in mesh.point_data:
            scalar = np.asarray(mesh.point_data[chosen_field]).reshape(-1).astype(np.float64)
            smin, smax = float(np.nanmin(scalar)), float(np.nanmax(scalar))
            global_scalar_min = smin if global_scalar_min is None else min(global_scalar_min, smin)
            global_scalar_max = smax if global_scalar_max is None else max(global_scalar_max, smax)
        else:
            scalar = None
            smin = smax = None

        # Kalthoff-Winkler plate lies primarily in x-z.
        max_points = 35000
        step = max(1, len(pts) // max_points)
        q = pts[::step]
        c = scalar[::step] if scalar is not None else None

        fig, ax = plt.subplots(figsize=(6.4, 6.4), dpi=100)
        if c is None:
            ax.scatter(q[:,0], q[:,2], s=1.0)
        else:
            sc = ax.scatter(q[:,0], q[:,2], s=1.0, c=c)
            fig.colorbar(sc, ax=ax, shrink=0.8, label=chosen_field)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlabel("x (m)")
        ax.set_ylabel("z (m)")
        ax.set_title(f"{a.case} — frame {seq+1}/{len(selected)}")
        ax.grid(True, alpha=0.2)
        fig.tight_layout()
        png = frame_dir / f"frame_{seq:04d}.png"
        fig.savefig(png)
        plt.close(fig)

        stats.append({
            "source": path.name,
            "particles": int(len(pts)),
            "bbox_min": [float(x) for x in pts.min(axis=0)],
            "bbox_max": [float(x) for x in pts.max(axis=0)],
            "scalar_min": smin,
            "scalar_max": smax
        })

    if not stats:
        raise SystemExit("no readable VTK frames")

    # Final selected frame becomes preview.
    import shutil
    shutil.copy2(frame_dir / f"frame_{len(stats)-1:04d}.png", a.output / "preview.png")

    result = {
        "case": a.case,
        "vtk_files": len(files),
        "rendered_frames": len(stats),
        "particle_count_min": particle_min,
        "particle_count_max": particle_max,
        "point_data_fields": sorted(all_fields),
        "fracture_scalar_candidate": chosen_field,
        "fracture_scalar_min": global_scalar_min,
        "fracture_scalar_max": global_scalar_max,
        "frames": stats,
        "errors": []
    }
    (a.output / "validation.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
