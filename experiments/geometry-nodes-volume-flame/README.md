# Geometry Nodes Volume Flame

Procedural flame pre-render built for the `tmp-blender` GitHub Actions → Colab workflow.

The flame is not a fluid simulation. Geometry Nodes moves a deterministic disk of seed points upward with per-point phase offsets, tapering and lateral oscillation. `Mesh to Points` converts the seed mesh to a point cloud, `Points to Volume` creates a density grid, and a Principled Volume material provides orange/blackbody emission.

## Geometry Nodes graph

```text
Seed mesh (420 vertices)
  -> Set Position
       ^ Position + Index + Scene Time
       ^ age = fract(index phase + time)
       ^ taper + sine/cosine wobble + upward motion
  -> Mesh to Points
  -> Points to Volume
       ^ animated per-point radius
       ^ voxel size 0.11 for pre-render
  -> Set Material (Principled Volume)
  -> Group Output
```

## Pre-render profile

- 480 × 360
- 24 fps
- 96 frames / 4 seconds
- requested EEVEE samples: 16
- 24 frames per chunk
- 4-way chunk parallelism
- PNG chunk cache + short-lived artifacts
- `.blend` committed to GitHub before frame rendering

This keeps the Geometry Nodes structure representative while intentionally reducing image quality for fast validation. The committed `.blend` is the handoff artifact for a later higher-quality Google Colab render.

## License / ライセンス

Code in this experiment is MIT-0. Generated Blender files, renders, videos, and other generated assets are CC0-1.0 unless otherwise noted. Third-party data/assets/source material remain subject to their original licenses and terms.

この実験のコードは MIT-0、生成された Blender ファイル・画像・動画・その他の生成アセットは、特記のない限り CC0-1.0 です。第三者由来のデータ・アセット・素材・ソースを利用している部分は、利用元のライセンスおよび利用条件に従います。

See ../../LICENSE and ../../LICENSES/.
