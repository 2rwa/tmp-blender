from __future__ import annotations

import json
import shutil
from pathlib import Path

import gdown

ROOT = Path.cwd()
DEST = ROOT / ".cache" / "quaternius-rpg-character-pack"
META = DEST / "_download.json"
URL = "https://drive.google.com/drive/folders/1MIRQXLfTd21HMI5rwOb6Xy0rv0xv1m8b?usp=sharing"

if DEST.exists():
    shutil.rmtree(DEST)
DEST.mkdir(parents=True, exist_ok=True)

gdown.download_folder(
    url=URL,
    output=str(DEST),
    quiet=False,
    use_cookies=False,
    remaining_ok=True,
)

all_files = [p for p in DEST.rglob("*") if p.is_file()]
character_files = [
    p for p in all_files
    if p.suffix.lower() in {".glb", ".gltf", ".fbx", ".blend"}
]

if not character_files:
    raise SystemExit("Quaternius download completed but no character source files were found")

META.write_text(
    json.dumps(
        {
            "source": URL,
            "downloaded_file_count": len(all_files),
            "character_source_count": len(character_files),
            "character_sources": [str(p.relative_to(DEST)) for p in sorted(character_files)],
        },
        indent=2,
    ) + "\n",
    encoding="utf-8",
)

print(f"QUATERNIUS_DOWNLOADED_FILES={len(all_files)}")
print(f"QUATERNIUS_CHARACTER_SOURCES={len(character_files)}")
for path in sorted(character_files)[:30]:
    print(f"QUATERNIUS_SOURCE={path.relative_to(DEST)}")
