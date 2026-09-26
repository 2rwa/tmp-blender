from __future__ import annotations

import json
import shutil
from pathlib import Path

import gdown

ROOT = Path.cwd()
DEST = ROOT / ".cache" / "quaternius-rpg-character-pack"
META = DEST / "_download.json"

# Official Quaternius Google Drive file IDs discovered from the pack's public folder.
FILES = {
    "Warrior.fbx": "1mPcA-6gGZYLiwD9gle7E1bPckGEkoapx",
    "Warrior_Texture.png": "1aCbtzIG86g5VJz63pAZ0a6_00e8nexyW",
}
PACK_PAGE = "https://quaternius.com/packs/rpgcharacters.html"
DRIVE_FOLDER = "https://drive.google.com/drive/folders/1MIRQXLfTd21HMI5rwOb6Xy0rv0xv1m8b?usp=sharing"

if DEST.exists():
    shutil.rmtree(DEST)
DEST.mkdir(parents=True, exist_ok=True)

downloaded = []
for name, file_id in FILES.items():
    target = DEST / name
    result = gdown.download(id=file_id, output=str(target), quiet=False)
    if not result or not target.is_file() or target.stat().st_size == 0:
        raise SystemExit(f"failed to download {name} from official Quaternius Drive")
    downloaded.append(
        {
            "name": name,
            "google_drive_file_id": file_id,
            "size_bytes": target.stat().st_size,
        }
    )

META.write_text(
    json.dumps(
        {
            "publisher": "Quaternius",
            "pack": "RPG Character Pack",
            "license": "CC0 1.0",
            "pack_page": PACK_PAGE,
            "official_drive_folder": DRIVE_FOLDER,
            "downloaded": downloaded,
        },
        indent=2,
    ) + "\n",
    encoding="utf-8",
)

print("QUATERNIUS_SELECTED_CHARACTER=Warrior")
for item in downloaded:
    print(f"QUATERNIUS_ASSET={item['name']}:{item['size_bytes']}")
