from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES_PATH = ROOT / "cases.json"
MODEL_PATH = ROOT / "models" / "UnitBox.obj"

def elasticity_block(spec: dict) -> dict:
    block = {
        "youngsModulus": float(spec["youngsModulus"]),
        "poissonsRatio": float(spec["poissonsRatio"]),
        "alpha": float(spec.get("alpha", 0.1)),
        "maxNeighbors": int(spec.get("maxNeighbors", 20)),
        "elasticityMaxIter": int(spec.get("elasticityMaxIter", 100)),
        "elasticityMaxError": float(spec.get("elasticityMaxError", 0.0001))
    }
    for key in ("fixedBoxMin", "fixedBoxMax", "volumeMaxError", "volumeMaxIter"):
        if key in spec:
            block[key] = spec[key]
    return block

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    config = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    case = config["cases"].get(args.case)
    if case is None:
        raise SystemExit(f"unknown case: {args.case}")
    defaults = config["defaults"]
    elastic = case["elasticity"]
    model = MODEL_PATH.resolve()

    material = {
        "id": "Fluid",
        "density0": 1000.0,
        "elasticityMethod": int(elastic["method"]),
        "viscosityMethod": 1,
        "Standard viscosity": {"viscosity": 0.01},
        elastic["name"]: elasticity_block(elastic)
    }

    scene = {
        "Configuration": {
            "pause": False,
            "stopAt": float(defaults["stop_at"]),
            "timeStepSize": 0.001,
            "numberOfStepsPerRenderUpdate": 2,
            "particleRadius": float(defaults["particle_radius"]),
            "simulationMethod": 4,
            "gravitation": case["gravity"],
            "cflMethod": 0,
            "cflFactor": 1.0,
            "cflMaxTimeStepSize": 0.003,
            "enableZSort": False,
            "boundaryHandlingMethod": 2,
            "enableVTKExport": True,
            "enableRigidBodyExport": False,
            "enableRigidBodyVTKExport": False,
            "dataExportFPS": float(defaults["fps"]),
            "particleAttributes": "velocity;density",
            "DFSPH": {
                "minIterations": 2,
                "maxIterations": 100,
                "maxError": 0.01,
                "maxIterationsV": 100,
                "maxErrorV": 0.1,
                "enableDivergenceSolver": True
            }
        },
        "Materials": [material],
        "RigidBodies": [{
            "geometryFile": str(model),
            "translation": [0.0, -0.10, 0.0],
            "rotationAxis": [1.0, 0.0, 0.0],
            "rotationAngle": 0.0,
            "scale": [5.0, 0.20, 5.0],
            "color": [0.15, 0.18, 0.22, 1.0],
            "isDynamic": False,
            "isWall": False,
            "mapInvert": False,
            "mapThickness": 0.0,
            "mapResolution": [32, 10, 32]
        }],
        "FluidBlocks": [{
            "id": "Fluid",
            "denseMode": 0,
            "start": block["start"],
            "end": block["end"],
            "initialVelocity": block.get("initialVelocity", [0.0, 0.0, 0.0])
        } for block in case["blocks"]]
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scene, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "case": args.case,
        "title": case["title"],
        "elasticity": elastic,
        "blocks": len(case["blocks"]),
        "particle_radius": defaults["particle_radius"],
        "stop_at": defaults["stop_at"]
    }, indent=2))

if __name__ == "__main__":
    main()
