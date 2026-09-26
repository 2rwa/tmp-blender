# Fluid Dam Break

Real Blender Mantaflow liquid simulation for the shared tmp-blender pipeline.

The experiment deliberately starts small enough for GitHub Actions:

- Blender 4.0.2
- liquid domain, FLIP method
- resolution max 32
- 42 frames at 24 fps
- Modular cache
- explicit Data bake followed by Mesh bake
- one central obstacle and one low barrier

Outputs:

- `fluid-dam-break.mp4` — rendered simulation
- `poster.png` — representative frame
- `fluid-sim.blend` — editable Mantaflow setup, saved after baking
- `fluid-result.blend` — self-contained frozen liquid mesh at the poster frame
- `fluid-cache/` — external Mantaflow cache, artifact/cache only
- `validation.json`

The two .blend files opt in to Git publication. Because this is a disposable test repository, they are committed directly up to a 95 MiB per-file safety threshold. Larger files remain in the Actions artifact; repository cleanup or extraction of useful results can be handled separately later.

## License / ライセンス

Code in this experiment is MIT-0. Generated Blender files, renders, videos, and other generated assets are CC0-1.0 unless otherwise noted. Third-party data/assets/source material remain subject to their original licenses and terms.

この実験のコードは MIT-0、生成された Blender ファイル・画像・動画・その他の生成アセットは、特記のない限り CC0-1.0 です。第三者由来のデータ・アセット・素材・ソースを利用している部分は、利用元のライセンスおよび利用条件に従います。

See ../../LICENSE and ../../LICENSES/.
