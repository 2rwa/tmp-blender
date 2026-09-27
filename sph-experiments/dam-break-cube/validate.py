from __future__ import annotations

import json
import math
import re
import struct
import sys
from pathlib import Path


POINTS_RE = re.compile(br"POINTS\s+(\d+)\s+(float|double)\s*\n")


def vtk_points(path: Path):
    data = path.read_bytes()
    match = POINTS_RE.search(data)
    if not match:
        raise SystemExit(f"POINTS header not found: {path}")
    count = int(match.group(1))
    kind = match.group(2)
    width = 4 if kind == b"float" else 8
    code = "f" if width == 4 else "d"
    start = match.end()
    raw = data[start : start + count * 3 * width]
    if len(raw) != count * 3 * width:
        raise SystemExit(f"truncated POINTS payload: {path}")
    values = struct.unpack(f">{count * 3}{code}", raw)
    return [
        (values[i], values[i + 1], values[i + 2])
        for i in range(0, len(values), 3)
    ]


def centroid(points):
    n = len(points)
    return tuple(sum(p[i] for p in points) / n for i in range(3))


def obj_counts(path: Path):
    vertices = 0
    faces = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("v "):
                vertices += 1
            elif line.startswith("f "):
                faces += 1
    return vertices, faces


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: validate.py OUTPUT_DIR")

    output = Path(sys.argv[1])
    vtk_dir = output / "vtk"
    def frame_number(path: Path) -> int:
        match = re.search(r"_(\d+)\.vtk$", path.name)
        if not match:
            raise SystemExit(f"cannot parse frame number: {path}")
        return int(match.group(1))

    particle_files = sorted(
        vtk_dir.glob("ParticleData_Fluid_*.vtk"),
        key=frame_number,
    )
    dynamic_files = sorted(
        vtk_dir.glob("rb_data_1_*.vtk"),
        key=frame_number,
    )
    surface = output / "surface-final.obj"
    log = output / "splash.log"

    if len(particle_files) < 3:
        raise SystemExit(f"expected >=3 particle frames, got {len(particle_files)}")
    if len(dynamic_files) < 3:
        raise SystemExit(f"expected >=3 dynamic rigid-body frames, got {len(dynamic_files)}")
    if not log.is_file() or log.stat().st_size == 0:
        raise SystemExit("missing splash.log")
    if not surface.is_file() or surface.stat().st_size == 0:
        raise SystemExit("missing reconstructed surface-final.obj")

    first_particles = vtk_points(particle_files[0])
    last_particles = vtk_points(particle_files[-1])
    if len(first_particles) < 100 or len(last_particles) < 100:
        raise SystemExit(
            f"unexpected particle counts: first={len(first_particles)} last={len(last_particles)}"
        )

    first_rb = centroid(vtk_points(dynamic_files[0]))
    last_rb = centroid(vtk_points(dynamic_files[-1]))
    displacement = math.dist(first_rb, last_rb)
    if displacement < 0.01:
        raise SystemExit(
            f"dynamic cube barely moved: displacement={displacement:.6f} m; "
            f"first={first_rb} last={last_rb}"
        )

    vertices, faces = obj_counts(surface)
    if vertices < 50 or faces < 50:
        raise SystemExit(
            f"surface mesh unexpectedly small: vertices={vertices} faces={faces}"
        )

    result = {
        "particle_frames": len(particle_files),
        "dynamic_rigid_body_frames": len(dynamic_files),
        "first_particle_count": len(first_particles),
        "last_particle_count": len(last_particles),
        "dynamic_cube_first_centroid": [round(v, 6) for v in first_rb],
        "dynamic_cube_last_centroid": [round(v, 6) for v in last_rb],
        "dynamic_cube_displacement_m": round(displacement, 6),
        "surface_obj_vertices": vertices,
        "surface_obj_faces": faces,
        "surface_obj_bytes": surface.stat().st_size,
    }

    summary = output / "summary.json"
    summary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
