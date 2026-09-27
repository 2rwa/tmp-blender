from __future__ import annotations

import json
from pathlib import Path

import bpy


ROOT = Path.cwd()
BASE = ROOT / "output" / "sph-blender-sequence"
MANIFEST = json.loads(
    (BASE / "sequence" / "surface-sequence.json").read_text(encoding="utf-8")
)
OUT = BASE / "blender" / "blend-validation.json"

objects = {
    obj.name: obj
    for obj in bpy.context.scene.objects
    if obj.name.startswith("FluidFrame_")
}

errors = []
observed = []
for record in MANIFEST["frames"]:
    frame = int(record["blender_frame"])
    expected = f"FluidFrame_{frame:04d}"
    bpy.context.scene.frame_set(frame)

    visible = []
    for name, obj in objects.items():
        scale = obj.scale
        if max(abs(scale.x), abs(scale.y), abs(scale.z)) > 0.5:
            visible.append(name)

    if visible != [expected]:
        errors.append(
            f"frame {frame}: expected [{expected}], got {visible}"
        )

    obj = objects.get(expected)
    if obj is None:
        errors.append(f"frame {frame}: missing object {expected}")
        continue

    verts = len(obj.data.vertices)
    faces = len(obj.data.polygons)
    if verts < 100 or faces < 100:
        errors.append(
            f"frame {frame}: unexpectedly small mesh vertices={verts} faces={faces}"
        )
    observed.append(
        {
            "frame": frame,
            "object": expected,
            "vertices": verts,
            "faces": faces,
            "visible": visible,
        }
    )

payload = {
    "frames": len(MANIFEST["frames"]),
    "fluid_objects": len(objects),
    "errors": errors,
    "observed": observed,
}
OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2))

if errors:
    raise SystemExit("saved Blender sequence validation failed")
