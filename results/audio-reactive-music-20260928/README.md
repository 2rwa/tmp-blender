# Audio-Reactive Music Visualizer 2026-09-28

A 20-second EEVEE music visualizer driven by frame-level analysis of assets/music/20260928_000.mp3. Low, mid, high, RMS, and transient energy animate a circular bar field, core, rings, lights, and camera; the source audio is muxed into the final MP4.

- source commit: `7e8f21919da9784bd78d92930f59b8fca52a2bc5`
- Actions run: `70` (`36407087514`)
- full artifact: `blender-audio-reactive-music-20260928`

## Blend files

- Git: [audio-reactive-music-20260928.blend](./audio-reactive-music-20260928.blend) (5,151,176 bytes)

![Latest preview](./preview.jpg)

## Validation

```json
{
  "video": "audio-reactive-music-20260928.mp4",
  "preview": {
    "size_bytes": 241800,
    "luminance_min": 0,
    "luminance_max": 251,
    "luminance_stddev": 58.851,
    "sha256": "a5ee52370eb4efd0609fbc3420265dc1bfdb2b3e89cd55fc950ce359319be0fe"
  },
  "movie": {
    "size_bytes": 1405987,
    "duration_seconds": 20.0,
    "video_codec": "h264",
    "audio_codec": "aac",
    "audio_sample_rate": "48000",
    "audio_channels": 2,
    "avg_frame_rate": "24/1",
    "nb_frames": "480",
    "sha256": "ac3c18e95fea1a7e18cf32159b69c36919f6bd36862ba6681046d680a91098cc"
  },
  "report": {
    "source": "assets/music/20260928_000.mp3",
    "source_sha256": "9f7355de1e6ec71a1431088afd245bfda8d3df1a26d8b159dc52a6b4895781c1",
    "beat_count": 20,
    "max_full": 1.263459,
    "max_transient": 1.5,
    "animated_objects": 44,
    "bar_count": 36,
    "keyframe_insert_calls": 49440,
    "blend_size_bytes": 5151176
  }
}
```

## License / ライセンス

Unless otherwise noted, generated assets in this result (including rendered images, video, and generated .blend files) are CC0-1.0. Source code and workflow files used to generate them are MIT-0.

特記のない限り、この成果物内の生成アセット（レンダリング画像、動画、生成された .blend ファイル等）は CC0-1.0、生成に使用したソースコードや workflow は MIT-0 です。

Third-party data, assets, or source material remain subject to their original licenses and terms. These repository licenses apply only to rights we are entitled to grant.

第三者のデータ・アセット・素材・ソースを利用している部分は、利用元のライセンスおよび利用条件に従います。このリポジトリのライセンスは、こちらが許諾できる権利にのみ適用されます。

See ../../LICENSE and ../../LICENSES/ for details.
