# Geometry Nodes Volume Flame

Animated low-cost pre-render of a procedural flame built from moving seed points, Points to Volume, and Principled Volume emission.

- source commit: `4035bd87918994ea9bce97f05c0f51d813b49839`
- Actions run: `25` (`36227169396`)
- full artifact: `blender-geometry-nodes-volume-flame`

## Blend files

- Git: [geometry-nodes-volume-flame.blend](./geometry-nodes-volume-flame.blend) (1,004,510 bytes)

![Latest preview](./preview.jpg)

## Validation

```json
{
  "video": "volume-flame.mp4",
  "preview": {
    "path": "output/preview.png",
    "size_bytes": 129788,
    "width": 480,
    "height": 360,
    "luminance_min": 0,
    "luminance_max": 239,
    "luminance_mean": 217.453,
    "luminance_stddev": 45.371,
    "unique_colors_64x48": 316,
    "sha256": "6e085a5593ddd5055a5a94bf2872aeba2a68da9b406f45fd0fd8b985372b92a5"
  },
  "movie": {
    "path": "output/volume-flame.mp4",
    "size_bytes": 43428,
    "width": 480,
    "height": 360,
    "duration_seconds": 4.0,
    "avg_frame_rate": "24/1",
    "nb_frames": "96",
    "sha256": "2876f876787cc936f5a51235cf6e3c0a246f109657157b62e1a94ed1ba58d358"
  },
  "geometry_nodes": {
    "node_group": "GN_VolumeFlame",
    "node_count": 35,
    "seed_point_count": 420,
    "voxel_size": 0.11,
    "frame_start": 1,
    "frame_end": 96,
    "fps": 24,
    "material_inputs_applied": [
      "Density",
      "Density Attribute",
      "Emission Strength",
      "Emission Color",
      "Blackbody Intensity",
      "Temperature",
      "Blackbody Tint"
    ],
    "blend_size_bytes": 1004510
  }
}
```

## License / ライセンス

Unless otherwise noted, generated assets in this result (including rendered images, video, and generated .blend files) are CC0-1.0. Source code and workflow files used to generate them are MIT-0.

特記のない限り、この成果物内の生成アセット（レンダリング画像、動画、生成された .blend ファイル等）は CC0-1.0、生成に使用したソースコードや workflow は MIT-0 です。

Third-party data, assets, or source material remain subject to their original licenses and terms. These repository licenses apply only to rights we are entitled to grant.

第三者のデータ・アセット・素材・ソースを利用している部分は、利用元のライセンスおよび利用条件に従います。このリポジトリのライセンスは、こちらが許諾できる権利にのみ適用されます。

See ../../LICENSE and ../../LICENSES/ for details.
