# Orbital Sculpture

Baseline image-render experiment used to verify the shared tmp-blender pipeline.

## Contract

- `scene.py` renders into repository-root `output/`.
- `validate.py` validates the real render and writes `output/validation.json`.
- `experiment.json` declares preview and required outputs.
- the shared workflow caches `output/`, uploads the full artifact, and commits a lightweight preview under `results/orbital-sculpture/`.

Expected full outputs:

- `render.png`
- `scene.blend`
- `validation.json`
- `blender-version.txt`

## License / ライセンス

Code in this experiment is MIT-0. Generated Blender files, renders, videos, and other generated assets are CC0-1.0 unless otherwise noted. Third-party data/assets/source material remain subject to their original licenses and terms.

この実験のコードは MIT-0、生成された Blender ファイル・画像・動画・その他の生成アセットは、特記のない限り CC0-1.0 です。第三者由来のデータ・アセット・素材・ソースを利用している部分は、利用元のライセンスおよび利用条件に従います。

See ../../LICENSE and ../../LICENSES/.
