# Geometry Nodes Ripple Grid Movie

Low-cost Blender 4.0.2 pre-render sample for checking animation, camera, Geometry Nodes evaluation, and timing before a higher-quality Colab render.

## Pre-render profile

- 480 x 360
- 24 fps
- 96 frames / 4 seconds
- requested EEVEE render samples: 16
- 24 frames per chunk
- PNG frame sequence
- up to 4 render chunks in parallel
- chunk PNGs cached for reuse
- same-run chunk artifacts used for deterministic MP4 assembly

The Geometry Nodes complexity stays representative of the source scene: a 31 x 31 grid is displaced by a radial time-varying sine wave, converted to points, populated with Icospheres, and realized.

## Pipeline

1. build the scene and save `geometry-nodes-movie.blend`;
2. commit the prepared Blend to `results/geometry-nodes-ripple-grid-movie/` before rendering;
3. render PNG frame chunks;
4. cache completed chunks and upload short-lived chunk artifacts;
5. assemble the PNG sequence with ffmpeg;
6. validate the preview, MP4 metadata, and evaluated Geometry Nodes mesh;
7. publish the final lightweight result and Pages preview.

The pre-render Blend is intentionally usable as the handoff to a later Colab render even if the GitHub Actions preview render fails.

## License / ライセンス

Code in this experiment is MIT-0. Generated Blender files, renders, videos, and other generated assets are CC0-1.0 unless otherwise noted. Third-party data/assets/source material remain subject to their original licenses and terms.

この実験のコードは MIT-0、生成された Blender ファイル・画像・動画・その他の生成アセットは、特記のない限り CC0-1.0 です。第三者由来のデータ・アセット・素材・ソースを利用している部分は、利用元のライセンスおよび利用条件に従います。

See ../../LICENSE and ../../LICENSES/.
