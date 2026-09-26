# tmp-blender

Temporary Blender experiment repository driven by GitHub Actions.

This repository is structured for throwing many unrelated Blender experiments at the same reusable render/cache/publish pipeline.

> **Resume / 再開:** [START HERE — handoff guide](docs/notes/START-HERE.md)
>
> 別の会話から再開するときは、まずこのファイルを読めば現在地と運用ルールを復元できます。

## Layout

```text
experiments/
  <experiment-id>/
    experiment.json
    scene.py
    validate.py

tools/
  experiment.py

results/
  <experiment-id>/

output/

.github/workflows/
  blender-experiment.yml
```

## Adding an experiment

Create `experiments/<experiment-id>/` with:

1. `scene.py` — render into repository-root `output/`.
2. `validate.py` — inspect the real result and write `output/validation.json`.
3. `experiment.json` — declare the preview image and required outputs.

Example:

```json
{
  "id": "water-dump",
  "title": "Water Dump",
  "description": "Short water simulation/render experiment.",
  "preview_source": "poster.png",
  "required_outputs": ["water.mp4", "poster.png", "scene.blend"]
}
```

A push that changes `experiments/<id>/` automatically runs that experiment. Shared workflow/tool changes use `orbital-sculpture` as a smoke test. Manual runs can select any experiment with `workflow_dispatch`.

## Cache / artifact / Git roles

- cache: avoid repeating expensive Blender work when the same Actions run is retried
- artifact: temporary full media and `.blend` output
- Git: lightweight preview and validation under `results/<id>/`

## Current experiments

- [orbital-sculpture](experiments/orbital-sculpture/) — baseline still-image render
- [water-dump](experiments/water-dump/) — short water-pour animation
- [fire-column](experiments/fire-column/) — lightweight animated flame column
- [fluid-dam-break](experiments/fluid-dam-break/) — Mantaflow liquid dam-break simulation
- [rigid-sphere-impact-1000](experiments/rigid-sphere-impact-1000/) — heavy sphere impact into 1000 rigid bodies
- [rigid-sphere-impact-1000-transparent-v2](experiments/rigid-sphere-impact-1000-transparent-v2/) — higher-quality sphere impact with transparent containment walls


## GitHub Pages gallery

Public preview gallery:

- https://2rwa.github.io/tmp-blender/

The workflow regenerates both root index.html and docs/, so the gallery works with either common branch-based Pages source setting. Short MP4 outputs up to 5 MiB are copied into results/<experiment>/media.mp4; large media and .blend files stay in Actions artifacts.


### Small .blend files in Git

Experiments may opt in to publishing selected .blend files through the `repo_blends` manifest field. For this temporary test repository, storage growth is not treated as an optimization target. Selected .blend files are committed directly under `results/<experiment>/` up to a 95 MiB per-file safety threshold, leaving only GitHub's hard single-file limit as the practical guardrail. Larger files remain in the Actions artifact. Cleanup/history rewriting can be handled separately from a local maintenance batch when needed.

## License / ライセンス

Unless otherwise noted:

- Source code, Python scripts, GitHub Actions workflows, and HTML are licensed under **MIT-0**.
- Blender files, rendered images, videos, and other generated assets are released under **CC0 1.0 Universal (CC0-1.0)**.
- If a file, experiment, or generated work uses third-party data, assets, source material, or other external content, those portions remain subject to the original source's license and terms. The licenses in this repository apply only to rights we are entitled to grant.
- A file-specific or experiment-specific license notice, when present, takes precedence for that material.

See [LICENSE](LICENSE) and [LICENSES/](LICENSES/).

特記のない限り：

- ソースコード、Python スクリプト、GitHub Actions workflow、HTML は **MIT-0** です。
- Blender ファイル、レンダリング画像、動画、その他の生成アセットは **CC0 1.0 Universal (CC0-1.0)** とします。
- 第三者のデータ、アセット、素材、ソース、その他の外部コンテンツを利用している部分は、利用元のライセンスおよび利用条件に従います。このリポジトリのライセンスは、こちらが許諾できる権利にのみ適用されます。
- 個別のファイルや実験に別のライセンス表記がある場合は、その表記が当該素材について優先されます。

詳細は [LICENSE](LICENSE) および [LICENSES/](LICENSES/) を参照してください。


## Engineering notes

- [START HERE — handoff / resume guide](docs/notes/START-HERE.md)
- [Architecture](docs/notes/architecture.md)
- [Experiment and implementation history](docs/notes/experiment-history.md)
- [Operating notes](docs/notes/operations.md)
