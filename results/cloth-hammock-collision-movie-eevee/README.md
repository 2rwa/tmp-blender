# Cloth Hammock Collision Movie EEVEE

An 8-second presentation-oriented extension of the cloth hammock experiment with two-stage sphere impacts, moving wind/turbulence, and a slow animated camera. Cloth physics is baked to shape keys before parallel EEVEE rendering.

- source commit: `828015e6f02f601722899cafb5e229b24ac00d8a`
- Actions run: `33` (`36236405528`)
- full artifact: `blender-cloth-hammock-collision-movie-eevee`

## Blend files

- Git: [cloth-hammock-collision-movie-eevee.blend](./cloth-hammock-collision-movie-eevee.blend) (5,123,800 bytes)

![Latest preview](./preview.jpg)

## Validation

```json
{
  "preview": {
    "path": "output/preview.png",
    "size_bytes": 222906,
    "width": 480,
    "height": 360,
    "luminance_min": 0,
    "luminance_max": 188,
    "luminance_mean": 58.711,
    "luminance_stddev": 62.431,
    "sha256": "8f643aacb66ddf2859d31658b93d5f71cfcb59fa33b325988cabc33f847a2b89"
  },
  "movie": {
    "path": "output/cloth-hammock-collision-movie-eevee.mp4",
    "size_bytes": 174567,
    "width": 480,
    "height": 360,
    "duration_seconds": 8.0,
    "avg_frame_rate": "24/1",
    "nb_frames": "192",
    "sha256": "ac294c5744ed09f0ddf98b52bb00bdaf2caebf2d37bba5bfd4ecb6c7883989c0"
  },
  "report": {
    "engine": "BLENDER_EEVEE",
    "vertex_count": 1575,
    "face_count": 1496,
    "pinned_vertex_count": 36,
    "baked_shape_keys": 192,
    "shape_key_count": 193,
    "simulation_seconds": 17.877,
    "colliders": [
      "BallAbove",
      "BallBelow"
    ],
    "effectors": [
      "CrossWind",
      "Turbulence"
    ],
    "blend_size_bytes": 5123800
  }
}
```

## License / ライセンス

Unless otherwise noted, generated assets in this result (including rendered images, video, and generated .blend files) are CC0-1.0. Source code and workflow files used to generate them are MIT-0.

特記のない限り、この成果物内の生成アセット（レンダリング画像、動画、生成された .blend ファイル等）は CC0-1.0、生成に使用したソースコードや workflow は MIT-0 です。

Third-party data, assets, or source material remain subject to their original licenses and terms. These repository licenses apply only to rights we are entitled to grant.

第三者のデータ・アセット・素材・ソースを利用している部分は、利用元のライセンスおよび利用条件に従います。このリポジトリのライセンスは、こちらが許諾できる権利にのみ適用されます。

See ../../LICENSE and ../../LICENSES/ for details.
