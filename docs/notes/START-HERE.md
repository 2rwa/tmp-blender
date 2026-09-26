# START HERE — tmp-blender handoff / 再開ガイド

Updated: 2026-09-26

This is the first file to read when resuming `2rwa/tmp-blender` from a new ChatGPT conversation.

別のChatGPT会話から `2rwa/tmp-blender` の作業を再開するときは、まずこのファイルを読んでください。

## Repository

- GitHub: https://github.com/2rwa/tmp-blender
- Pages gallery: https://2rwa.github.io/tmp-blender/
- Default branch: `main`
- Purpose: disposable public Blender experiment repository driven by GitHub Actions
- Current Blender runtime: Blender 4.0.2 on GitHub-hosted Linux runner via Xvfb/software GL

This repository is intentionally allowed to grow. Do not optimize repository size during normal experiments unless explicitly asked. Useful work can later be copied elsewhere and the repository can be cleaned/re-written/deleted in a separate maintenance batch.

このrepoは一時的な公開テスト用です。通常の実験中は容量最適化を優先しません。必要な成果物は後で別repoへ移し、掃除は別バッチで行う方針です。

## Current state

The most recent completed experiment is:

`rigid-sphere-impact-1000-transparent-v2`

It is a higher-quality follow-up to `rigid-sphere-impact-1000`.

Configuration:

- 1000 active rigid-body cubes
- one 22 kg active impact sphere
- floor + three transparent physical containment walls
- front/camera side open
- 960 × 540
- 96 frames
- 24 fps
- `RigidBodyWorld.substeps_per_frame = 12`
- `RigidBodyWorld.solver_iterations = 30`

GitHub Actions run #18 completed successfully:

https://github.com/2rwa/tmp-blender/actions/runs/36219589354

Published result:

https://github.com/2rwa/tmp-blender/tree/main/results/rigid-sphere-impact-1000-transparent-v2

Observed validation:

- MP4: 459,528 bytes
- duration: 4.0 s
- preview: 960 × 540
- `rigid-sim.blend`: 9,613,412 bytes
- `rigid-result.blend`: 9,613,412 bytes
- both `.blend` files are committed to Git
- Pages deployment succeeded

The user described the transparent-wall result as "良い感じ".

## Previous experiments

### orbital-sculpture

Baseline still-image smoke test.

### water-dump

Cheap water-like animation using Ocean + procedural/animated geometry. Not a full Mantaflow simulation.

### fire-column

Cheap stylized flame animation using emissive geometry/glow/sparks. Not a full Mantaflow gas simulation.

### fluid-dam-break

Actual Mantaflow liquid simulation.

- FLIP liquid
- resolution max 32
- Data bake + Mesh bake
- run #15 succeeded
- two Blender files published to Git
- large simulation cache kept outside Git

### rigid-sphere-impact-1000

First 1000-body impact version.

- 1000 cubes
- one 18 kg sphere
- opaque side/rear walls
- 640 × 360
- 72 frames
- run #17 succeeded
- result and two `.blend` files published to Git

The opaque walls were visually distracting, which motivated transparent-wall v2.

## Critical operating rules

### Long-running tasks

For simulations/renders likely to take more than roughly 30 seconds:

1. commit/push experiment changes,
2. verify Actions discovery and cheap preflight,
3. check for immediate Blender/Python/API failures,
4. once real long-running simulation/render work has started, stop polling and return the conversation turn,
5. inspect the run on the next user turn.

Do not block the conversation by repeatedly polling a long Actions job.

### Expensive work checkpointing

The workflow intentionally saves the raw render checkpoint before validation.

If rendering succeeds but validation fails:

- do not rerender automatically,
- fix `validate.py` where possible,
- validator/README/manifest files are excluded from the expensive render hash,
- reuse the saved render checkpoint.

### Blender API version

Target Blender 4.0.2 exactly. Do not assume API names from newer Blender releases.

Known examples:

- RigidBodyWorld: use `substeps_per_frame`, not `steps_per_second`
- prior experiments also encountered version-specific modifier/property differences

### Result publishing

Experiment manifest may contain:

```json
"repo_blends": [
  "example-sim.blend",
  "example-result.blend"
]
```

Current thresholds/policy:

- selected `.blend` files up to 95 MiB/file -> Git
- MP4 up to 5 MiB -> `results/<id>/media.mp4` for Pages
- large caches/intermediates -> Actions cache/artifact
- repository growth is acceptable for this temporary repo

## Pipeline overview

`.github/workflows/blender-experiment.yml`

Stages:

1. `discover`
2. `render`
3. `publish`
4. `pages` / `deploy_pages`

Important tooling:

- `tools/experiment.py`
  - experiment discovery
  - output checks
  - result publishing
  - selected `.blend` Git publication
- `tools/build_pages.py`
  - root/docs gallery generation

A change under one `experiments/<id>/` folder should normally run only that experiment.

Shared workflow/tool-only changes use `orbital-sculpture` as a smoke test.

## Licensing

Default:

- code/scripts/workflows/HTML: MIT-0
- generated Blender files/images/video/assets: CC0-1.0
- third-party data/assets/source material: original license/terms apply

See:

- `LICENSE`
- `LICENSES/`

Do not relicense third-party material that the repository authors do not control.

## Where to read next

- Architecture: `docs/notes/architecture.md`
- Experiment/history log: `docs/notes/experiment-history.md`
- Operational rules: `docs/notes/operations.md`

## Suggested next directions

There is no mandatory pending task. The current transparent-wall v2 is complete.

Natural next experiments include:

- actual Mantaflow smoke/fire (as opposed to the lightweight procedural fire-column)
- cloth over rigid bodies / wind interaction
- soft-body jelly collision
- Dynamic Paint ripples or wet trails
- particle/emitter stress tests
- Hair Curves / Geometry Nodes hair experiments
- larger rigid-body counts or alternative impact geometries

When starting a new experiment, create a new experiment ID rather than overwriting a successful prior experiment unless the user explicitly asks to revise it.

## Copy/paste prompt for a new ChatGPT conversation

```text
GitHub repo 2rwa/tmp-blender の作業を再開してください。

最初に main の
docs/notes/START-HERE.md
を読み、必要なら
docs/notes/architecture.md
docs/notes/experiment-history.md
docs/notes/operations.md
も確認してください。

GitHubをsource of truthとして現在状態を確認してから進めてください。
長時間のBlender render/simulationはGitHub Actionsへ投げ、preflightと即時エラーだけ確認し、本処理に入ったら会話を返してください。
validatorだけの失敗では、render checkpointが使えるなら再レンダーしないでください。
tmp-blenderは一時repoなので、この作業ではrepo容量を気にしすぎなくて構いません。
```

## Shortest possible resume instruction

A new conversation can usually start with only:

```text
2rwa/tmp-blender の docs/notes/START-HERE.md を読んで、GitHubの現在状態を確認して作業を再開して。
```
