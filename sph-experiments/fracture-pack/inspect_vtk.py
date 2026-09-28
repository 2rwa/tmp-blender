from __future__ import annotations
import argparse, json, math, shutil
from pathlib import Path
import numpy as np

CANDIDATE_WORDS = ("phase", "fract", "damage", "crack", "pf")

def read_legacy_polydata(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if not any(line.strip().upper() == "DATASET POLYDATA" for line in lines[:12]):
        raise ValueError(f"expected legacy ASCII POLYDATA: {path}")

    points = None
    scalars = {}
    i = 0
    point_count = None
    while i < len(lines):
        line = lines[i].strip()
        up = line.upper()
        if up.startswith("POINTS "):
            parts = line.split()
            n = int(parts[1])
            vals = []
            i += 1
            while i < len(lines) and len(vals) < n * 3:
                vals.extend(float(x) for x in lines[i].split())
                i += 1
            if len(vals) < n * 3:
                raise ValueError(f"truncated POINTS in {path}")
            points = np.asarray(vals[: n * 3], dtype=np.float64).reshape(n, 3)
            continue
        if up.startswith("POINT_DATA "):
            point_count = int(line.split()[1])
            i += 1
            continue
        if point_count is not None and up.startswith("SCALARS "):
            parts = line.split()
            name = parts[1]
            ncomp = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else 1
            i += 1
            if i < len(lines) and lines[i].strip().upper().startswith("LOOKUP_TABLE"):
                i += 1
            need = point_count * ncomp
            vals = []
            while i < len(lines) and len(vals) < need:
                probe = lines[i].strip()
                probe_up = probe.upper()
                if probe_up.startswith(("SCALARS ", "VECTORS ", "FIELD ", "CELL_DATA ", "POINT_DATA ")):
                    break
                if probe:
                    vals.extend(float(x) for x in probe.split())
                i += 1
            if len(vals) >= need:
                arr = np.asarray(vals[:need], dtype=np.float64).reshape(point_count, ncomp)
                if ncomp == 1:
                    arr = arr[:, 0]
                scalars[name] = arr
            continue
        i += 1

    if points is None:
        raise ValueError(f"POINTS section missing in {path}")
    return points, scalars

def find_scalar(scalars):
    scored = []
    for key, arr in scalars.items():
        if np.asarray(arr).ndim != 1:
            continue
        score = sum(w in key.lower() for w in CANDIDATE_WORDS)
        if score:
            scored.append((score, key, np.asarray(arr, dtype=np.float64)))
    if not scored:
        return None, None
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    _, key, arr = scored[0]
    return key, arr

def main():
    p = argparse.ArgumentParser()
    p.add_argument("vtk_dir", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--case", required=True)
    p.add_argument("--max-render-frames", type=int, default=18)
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
        pts, scalars = read_legacy_polydata(path)
        all_fields.update(scalars.keys())
        particle_min = len(pts) if particle_min is None else min(particle_min, len(pts))
        particle_max = len(pts) if particle_max is None else max(particle_max, len(pts))

        key, candidate = find_scalar(scalars)
        if chosen_field is None and key is not None:
            chosen_field = key
        scalar = scalars.get(chosen_field) if chosen_field else candidate
        if scalar is not None and np.asarray(scalar).ndim == 1 and len(scalar) == len(pts):
            scalar = np.asarray(scalar, dtype=np.float64)
            smin, smax = float(np.nanmin(scalar)), float(np.nanmax(scalar))
            global_scalar_min = smin if global_scalar_min is None else min(global_scalar_min, smin)
            global_scalar_max = smax if global_scalar_max is None else max(global_scalar_max, smax)
        else:
            scalar = None
            smin = smax = None

        max_points = 40000
        step = max(1, len(pts) // max_points)
        q = pts[::step]
        c = scalar[::step] if scalar is not None else None

        fig, ax = plt.subplots(figsize=(6.4, 6.4), dpi=100)
        if c is None:
            ax.scatter(q[:, 0], q[:, 2], s=0.8)
        else:
            sc = ax.scatter(q[:, 0], q[:, 2], s=0.8, c=c)
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
