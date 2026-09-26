from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = ROOT / "experiments"
RESULTS = ROOT / "results"
DOCS = ROOT / "docs"
GITHUB_BASE = "https://github.com/2rwa/tmp-blender"


def load_entries() -> list[dict]:
    entries = []
    if not RESULTS.exists():
        return entries

    tick = chr(96)
    for result_dir in sorted(p for p in RESULTS.iterdir() if p.is_dir()):
        experiment_id = result_dir.name
        manifest_path = EXPERIMENTS / experiment_id / "experiment.json"
        validation_path = result_dir / "validation.json"
        preview_path = result_dir / "preview.jpg"
        readme_path = result_dir / "README.md"

        if not (manifest_path.is_file() and validation_path.is_file() and preview_path.is_file()):
            continue

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validation = json.loads(validation_path.read_text(encoding="utf-8"))

        source_commit = ""
        run_number = ""
        run_id = ""
        if readme_path.is_file():
            text = readme_path.read_text(encoding="utf-8")
            m = re.search(r"- source commit: " + re.escape(tick) + r"([0-9a-f]+)" + re.escape(tick), text)
            if m:
                source_commit = m.group(1)
            m = re.search(
                r"- Actions run: " + re.escape(tick) + r"([^" + tick + r"]+)" + re.escape(tick)
                + r" \(" + re.escape(tick) + r"([^" + tick + r"]+)" + re.escape(tick) + r"\)",
                text,
            )
            if m:
                run_number, run_id = m.group(1), m.group(2)

        blend_files = sorted(p.name for p in result_dir.glob("*.blend"))

        entries.append({
            "id": experiment_id,
            "title": manifest.get("title", experiment_id),
            "description": manifest.get("description", ""),
            "validation": validation,
            "source_commit": source_commit,
            "run_number": run_number,
            "run_id": run_id,
            "has_media": (result_dir / "media.mp4").is_file(),
            "blend_files": blend_files,
        })
    return entries


def stat_rows(validation: dict) -> str:
    preferred = [
        "duration_seconds",
        "fps",
        "width",
        "height",
        "video_size_bytes",
        "poster_luminance_stddev",
        "bright_pixel_ratio",
        "warm_pixel_ratio",
        "poster_unique_colors_64x36",
    ]
    rows = []
    for key in preferred:
        if key not in validation:
            continue
        value = validation[key]
        if key == "video_size_bytes":
            value = f"{int(value):,} bytes"
        rows.append(
            f"<tr><th>{html.escape(key)}</th><td>{html.escape(str(value))}</td></tr>"
        )
    return "".join(rows)


def render(entries: list[dict], docs_mode: bool) -> str:
    cards = []
    for entry in entries:
        eid = entry["id"]
        asset_root = f"assets/{eid}" if docs_mode else f"results/{eid}"

        if entry["has_media"]:
            visual = (
                f'<video controls autoplay muted loop playsinline poster="{asset_root}/preview.jpg">'
                f'<source src="{asset_root}/media.mp4" type="video/mp4">'
                f'</video>'
            )
        else:
            visual = f'<img src="{asset_root}/preview.jpg" alt="{html.escape(entry["title"])} preview">'

        links = [
            f'<a href="{asset_root}/preview.jpg">preview</a>',
            f'<a href="{asset_root}/validation.json">validation</a>',
            f'<a href="{GITHUB_BASE}/tree/main/experiments/{eid}">source</a>',
            f'<a href="{GITHUB_BASE}/tree/main/results/{eid}">result</a>',
        ]
        if entry["has_media"]:
            links.insert(1, f'<a href="{asset_root}/media.mp4">mp4</a>')
        for blend_name in entry["blend_files"]:
            links.append(
                f'<a href="{GITHUB_BASE}/blob/main/results/{eid}/{blend_name}">{html.escape(blend_name)}</a>'
            )
        if entry["run_id"]:
            links.append(
                f'<a href="{GITHUB_BASE}/actions/runs/{entry["run_id"]}">Actions #{html.escape(entry["run_number"])}</a>'
            )

        source = ""
        if entry["source_commit"]:
            short = entry["source_commit"][:10]
            source = (
                f'<p class="source">source <a href="{GITHUB_BASE}/commit/{entry["source_commit"]}">'
                f'{short}</a></p>'
            )

        cards.append(f"""
        <article class="card">
          <div class="visual">{visual}</div>
          <div class="body">
            <h2>{html.escape(entry["title"])}</h2>
            <p class="id">{html.escape(eid)}</p>
            <p>{html.escape(entry["description"])}</p>
            {source}
            <table>{stat_rows(entry["validation"])}</table>
            <p class="links">{" · ".join(links)}</p>
          </div>
        </article>
        """)

    return f"""<!-- SPDX-License-Identifier: MIT-0 -->
<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark">
<title>tmp-blender gallery</title>
<style>
:root {{ font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color:#edf3f8; background:#0a0d12; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:radial-gradient(circle at top,#162231 0,#0a0d12 42rem); }}
header {{ max-width:1200px; margin:auto; padding:42px 22px 18px; }}
h1 {{ margin:0 0 8px; font-size:clamp(2rem,5vw,4rem); letter-spacing:-.04em; }}
header p {{ margin:0; color:#9fb2c5; }}
main {{ max-width:1200px; margin:auto; padding:22px; display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:22px; }}
.card {{ overflow:hidden; border:1px solid #253244; border-radius:18px; background:#101722d9; box-shadow:0 18px 50px #0007; }}
.visual {{ aspect-ratio:16/9; background:#000; display:flex; align-items:center; justify-content:center; }}
.visual img,.visual video {{ width:100%; height:100%; object-fit:cover; display:block; }}
.body {{ padding:18px; }}
h2 {{ margin:0; font-size:1.35rem; }}
.id,.source {{ color:#8297aa; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:.82rem; }}
table {{ width:100%; border-collapse:collapse; margin:14px 0; font-size:.86rem; }}
th,td {{ padding:5px 0; border-bottom:1px solid #202d3d; text-align:left; }}
th {{ color:#8fa4b8; font-weight:500; }}
td {{ text-align:right; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
a {{ color:#78c4ff; text-decoration:none; }}
a:hover {{ text-decoration:underline; }}
.links {{ font-size:.88rem; line-height:1.8; }}
footer {{ max-width:1200px; margin:auto; padding:10px 22px 44px; color:#73879a; }}
</style>
</head>
<body>
<header>
  <h1>tmp-blender</h1>
  <p>GitHub Actionsで生成したBlender実験の公開ギャラリー。preview / validation / 短い動画を直接確認できます。</p>
</header>
<main>
{''.join(cards)}
</main>
<footer>Generated from committed results. Code: MIT-0 · Generated assets: CC0-1.0 · Third-party source licenses/terms apply where applicable. / コード: MIT-0 · 生成物: CC0-1.0 · 第三者由来部分は利用元のライセンス・利用条件に従います。</footer>
</body>
</html>
"""


def copy_docs_assets(entries: list[dict]) -> None:
    assets = DOCS / "assets"
    if assets.exists():
        shutil.rmtree(assets)
    assets.mkdir(parents=True, exist_ok=True)

    for entry in entries:
        eid = entry["id"]
        src = RESULTS / eid
        dst = assets / eid
        dst.mkdir(parents=True, exist_ok=True)
        for name in ("preview.jpg", "validation.json", "media.mp4"):
            source = src / name
            if source.is_file():
                shutil.copy2(source, dst / name)


def main() -> None:
    entries = load_entries()
    (ROOT / "index.html").write_text(render(entries, docs_mode=False), encoding="utf-8")
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")

    DOCS.mkdir(parents=True, exist_ok=True)
    copy_docs_assets(entries)
    (DOCS / "index.html").write_text(render(entries, docs_mode=True), encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")

    print(f"built Pages gallery for {len(entries)} experiments")


if __name__ == "__main__":
    main()
