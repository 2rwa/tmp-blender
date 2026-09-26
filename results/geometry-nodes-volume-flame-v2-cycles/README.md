# Geometry Nodes Volume Flame v2 Cycles

Diagnostic comparison render of the v2 procedural flame using Cycles CPU to isolate renderer-vs-node-setup differences.

- source commit: `54e08f2fcc65916212027f6c0ab1ac510bb34106`
- Actions run: `31` (`36234997583`)
- full artifact: `blender-geometry-nodes-volume-flame-v2-cycles`

## Blend files

- Git: [geometry-nodes-volume-flame-v2-cycles.blend](./geometry-nodes-volume-flame-v2-cycles.blend) (1,161,840 bytes)

![Latest preview](./preview.jpg)

## Validation

```json
{
  "video": "volume-flame-v2-cycles.mp4",
  "preview": {
    "path": "output/preview.png",
    "width": 480,
    "height": 360,
    "luminance_min": 0,
    "luminance_max": 239,
    "luminance_mean": 65.781,
    "luminance_stddev": 79.079,
    "warm_ratio": 0.29593,
    "white_ratio": 0.0,
    "sha256": "6ed1b075f9391342309fac1b2ea7b11640e3bd7b92e1b0723470d478b52419d3"
  },
  "movie": {
    "path": "output/volume-flame-v2-cycles.mp4",
    "width": 480,
    "height": 360,
    "duration_seconds": 2.0,
    "avg_frame_rate": "24/1",
    "nb_frames": "48",
    "sha256": "dc0ed2c0ebbc1e5cc7a24432f31ba9b055d57a5e46130402558106c6869f866e"
  },
  "report": {
    "frame_start": 1,
    "frame_end": 48,
    "fps": 24,
    "resolution_x": 480,
    "resolution_y": 360,
    "requested_render_samples": 16,
    "effective_render_samples": 12,
    "seed_counts": [
      520,
      180
    ],
    "blend_size_bytes": 1161840,
    "materials": {
      "outer": {
        "name": "OuterFlameMaterial",
        "density": 0.2199999988079071,
        "emission_strength": 1.100000023841858,
        "blackbody_intensity": 0.2800000011920929,
        "temperature": 1425.0
      },
      "core": {
        "name": "CoreFlameMaterial",
        "density": 0.10000000149011612,
        "emission_strength": 1.5499999523162842,
        "blackbody_intensity": 0.46000000834465027,
        "temperature": 1980.0
      }
    }
  }
}
```

## License / ライセンス

Unless otherwise noted, generated assets in this result (including rendered images, video, and generated .blend files) are CC0-1.0. Source code and workflow files used to generate them are MIT-0.

特記のない限り、この成果物内の生成アセット（レンダリング画像、動画、生成された .blend ファイル等）は CC0-1.0、生成に使用したソースコードや workflow は MIT-0 です。

Third-party data, assets, or source material remain subject to their original licenses and terms. These repository licenses apply only to rights we are entitled to grant.

第三者のデータ・アセット・素材・ソースを利用している部分は、利用元のライセンスおよび利用条件に従います。このリポジトリのライセンスは、こちらが許諾できる権利にのみ適用されます。

See ../../LICENSE and ../../LICENSES/ for details.
