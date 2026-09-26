from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
from pathlib import Path

ROOT = Path.cwd()
DEST = ROOT / ".cache" / "quaternius-rpg-character-pack"
META = DEST / "_download.json"

PACK_PAGE = "https://quaternius.com/packs/rpgcharacters.html"
OFFICIAL_DRIVE = "https://drive.google.com/drive/folders/1MIRQXLfTd21HMI5rwOb6Xy0rv0xv1m8b?usp=sharing"

# Temporary public mirror of the CC0 Quaternius RPG Character Pack Warrior.
# The official Google Drive was quota-limited during Actions runs #46/#47.
MIRROR_URL = (
    "https://raw.githubusercontent.com/Hakhyun-Kim/constellation-defense/main/"
    "assets/models/quaternius-warrior.glb"
)
MIRROR_REPO = "https://github.com/Hakhyun-Kim/constellation-defense"
TARGET = "Warrior.glb"

if DEST.exists():
    shutil.rmtree(DEST)
DEST.mkdir(parents=True, exist_ok=True)

target = DEST / TARGET
urllib.request.urlretrieve(MIRROR_URL, target)

if not target.is_file() or target.stat().st_size < 100_000:
    raise SystemExit(f"mirrored Warrior GLB missing or suspiciously small: {target}")

sha256 = hashlib.sha256(target.read_bytes()).hexdigest()

META.write_text(
    json.dumps(
        {
            "publisher": "Quaternius",
            "pack": "RPG Character Pack",
            "license": "CC0 1.0",
            "pack_page": PACK_PAGE,
            "official_drive_folder": OFFICIAL_DRIVE,
            "acquisition": {
                "method": "public GitHub mirror",
                "mirror_repository": MIRROR_REPO,
                "mirror_url": MIRROR_URL,
                "reason": "official Google Drive quota-limited during CI",
            },
            "downloaded": {
                "name": TARGET,
                "size_bytes": target.stat().st_size,
                "sha256": sha256,
            },
        },
        indent=2,
    ) + "\n",
    encoding="utf-8",
)

print("QUATERNIUS_SELECTED_CHARACTER=Warrior")
print(f"QUATERNIUS_ASSET={TARGET}:{target.stat().st_size}")
print(f"QUATERNIUS_ASSET_SHA256={sha256}")
