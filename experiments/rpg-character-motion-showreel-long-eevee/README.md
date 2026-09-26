# Quaternius RPG Character Motion Showreel — long EEVEE test

Long-form GitHub Actions stress test based on the successful `rpg-character-pack-smoke-test-eevee` experiment.

## Purpose

This intentionally jumps to a substantially longer render so failures become visible early.

- character: Quaternius RPG Character Pack — Warrior
- imported actions expected: 13
- allocation: 144 frames / 6 seconds per action
- total: 1,872 frames / 78 seconds
- fps: 24
- resolution: 480 x 360
- renderer: EEVEE
- camera: fixed
- render chunk: 120 frames
- expected render chunks: 16

Each imported action is placed sequentially on one NLA track. The action's native frame range is repeated to fill its six-second segment rather than stretching a short motion across six seconds.

The report records every action name, native frame range, repeat factor, and assigned segment.

## Source

- Publisher: Quaternius
- Pack: RPG Character Pack
- Original license: CC0 1.0
- Pack page: https://quaternius.com/packs/rpgcharacters.html
- Runtime GLB acquisition: same verified public GitHub mirror used by the successful smoke test.

The official Google Drive was quota-limited during the earlier CI experiment, so this reuses the known-good mirror acquisition path.

## What this test is trying to break

- NLA sequencing across all imported actions
- a much longer prepared timeline
- 1,872-frame chunk planning
- parallel render fan-out
- artifact transfer across many chunks
- ffmpeg assembly of a 78-second movie
- long-form duration/frame validation
- result publishing and Pages deployment

Failure is useful: preserve the failing stage and logs before changing the design.
