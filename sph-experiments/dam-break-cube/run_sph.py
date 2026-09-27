from __future__ import annotations

import argparse
from pathlib import Path

import pysplishsplash as sph


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scene", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--stop-at", type=float, default=1.0)
    args = parser.parse_args()

    scene = args.scene.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"SPH_SCENE={scene}")
    print(f"SPH_OUTPUT={output_dir}")
    print(f"SPH_STOP_AT={args.stop_at}")

    base = sph.Exec.SimulatorBase()
    base.init(
        sceneFile=str(scene),
        useGui=False,
        initialPause=False,
        useCache=False,
        stopAt=float(args.stop_at),
        outputDir=str(output_dir),
    )
    base.run()
    print("SPH_RUN_COMPLETE")


if __name__ == "__main__":
    main()
