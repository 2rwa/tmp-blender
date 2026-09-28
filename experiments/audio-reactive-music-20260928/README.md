# Audio-Reactive Music Visualizer 2026-09-28

This experiment turns `assets/music/20260928_000.mp3` into a short Blender movie that reacts to the actual audio signal.

## Pipeline

1. `prepare_audio.py` decodes the first 20 seconds with `ffmpeg`.
2. It measures frame-level full-band, low (<180 Hz), mid (180–2500 Hz), and high (>2500 Hz) RMS plus a transient signal.
3. `scene.py` bakes those values into 36 radial bars, three rings, a central pulse object, three lights, and the camera.
4. GitHub Actions renders PNG chunks in parallel.
5. The assembler encodes H.264 and muxes the source music excerpt as AAC.
6. `validate.py` checks the real preview, duration, video dimensions, audio stream, analysis metadata, and animation counts.

This is a first visual prototype intended to establish a reusable audio-analysis → Blender-keyframes → parallel-render → audio-mux path.
