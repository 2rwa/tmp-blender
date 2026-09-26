# Quaternius RPG Character Pack smoke test

Headless Blender/GitHub Actions import test for the **Quaternius RPG Character Pack**.

## Source and license

- Publisher: Quaternius
- Pack: RPG Character Pack
- Pack page: https://quaternius.com/packs/rpgcharacters.html
- License shown on the pack page: CC0 1.0
- Official download folder: https://drive.google.com/drive/folders/1MIRQXLfTd21HMI5rwOb6Xy0rv0xv1m8b?usp=sharing

The upstream asset files are **not vendored into this repository**. The official Google Drive hit its public download quota in Actions runs #46 and #47, even for a single Warrior FBX. The smoke test therefore uses a public GitHub mirror of the same CC0 Quaternius Warrior as a packed GLB, while preserving the original Quaternius pack page and license metadata.

## Test

1. Download `assets/models/quaternius-warrior.glb` from the public `Hakhyun-Kim/constellation-defense` mirror.
2. Import the packed Warrior GLB.
3. Import it in Blender 4.0.2.
4. Require at least one mesh, armature, material, and animation action.
5. Prefer an Idle action, falling back to Walk/Run or the richest imported action.
6. Normalize the character to about 2.6 Blender units tall.
7. Pack external assets into the prepared `.blend`.
8. Render 144 frames / 6 seconds through the existing parallel movie pipeline.
9. Validate the prepared scene, preview, and MP4 rather than accepting process exit alone.

This is intentionally a smoke test. Once the asset survives the headless pipeline reliably, later experiments can combine the character with rigid bodies, cloth, metaballs, and other physics.


## Temporary mirror

- Mirror repository: https://github.com/Hakhyun-Kim/constellation-defense
- Mirrored file: `assets/models/quaternius-warrior.glb`
- That repository's credits identify the runtime Warrior model as originating from Quaternius' RPG Character Pack under CC0 1.0.
- The mirror is used only because the official Google Drive returned quota errors in CI; Quaternius remains the recorded asset publisher/source.


## Validation note

The first successful render compressed to about 21.6 KB because the selected `Idle_Attacking` action and studio camera are visually simple. The MP4 minimum-size guard was therefore reduced from 25 KB to 15 KB; character/rig/material/action semantics remain the primary correctness checks.
