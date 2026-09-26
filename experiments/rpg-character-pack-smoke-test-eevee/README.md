# Quaternius RPG Character Pack smoke test

Headless Blender/GitHub Actions import test for the **Quaternius RPG Character Pack**.

## Source and license

- Publisher: Quaternius
- Pack: RPG Character Pack
- Pack page: https://quaternius.com/packs/rpgcharacters.html
- License shown on the pack page: CC0 1.0
- Official download folder: https://drive.google.com/drive/folders/1MIRQXLfTd21HMI5rwOb6Xy0rv0xv1m8b?usp=sharing

The upstream asset files are **not vendored into this repository**. The prepare job downloads the official public folder at run time.

## Test

1. Download the official pack with `gdown`.
2. Prefer a Warrior/Knight-like GLB/glTF asset, then FBX as fallback.
3. Import it in Blender 4.0.2.
4. Require at least one mesh, armature, material, and animation action.
5. Prefer an Idle action, falling back to Walk/Run or the richest imported action.
6. Normalize the character to about 2.6 Blender units tall.
7. Pack external assets into the prepared `.blend`.
8. Render 144 frames / 6 seconds through the existing parallel movie pipeline.
9. Validate the prepared scene, preview, and MP4 rather than accepting process exit alone.

This is intentionally a smoke test. Once the asset survives the headless pipeline reliably, later experiments can combine the character with rigid bodies, cloth, metaballs, and other physics.
