from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES_PATH = ROOT / "cases.json"
MODEL_PATH = ROOT / "models" / "UnitBox.obj"

def material_record(phase_id: str, spec: dict) -> dict:
    return {
        "id": phase_id,
        "density0": float(spec["density"]),
        "viscosityMethod": 1,
        "colorMapType": 1,
        "Standard viscosity": {"viscosity": float(spec["viscosity"])},
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    config = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = config["cases"]
    if args.case not in cases:
        raise SystemExit(f"unknown case {args.case!r}; choose from {sorted(cases)}")

    defaults = config["defaults"]
    case = cases[args.case]
    model = MODEL_PATH.resolve()
    if not model.is_file():
        raise SystemExit(f"missing model: {model}")

    scene = {
        "Configuration": {
            "pause": False,
            "stopAt": float(defaults["stop_at"]),
            "timeStepSize": 0.001,
            "numberOfStepsPerRenderUpdate": 2,
            "particleRadius": float(defaults["particle_radius"]),
            "simulationMethod": 4,
            "gravitation": case["gravity"],
            "cflMethod": 1,
            "cflFactor": 0.5,
            "cflMaxTimeStepSize": 0.005,
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
                "enableDivergenceSolver": True,
            },
        },
        "Materials": [
            material_record("PhaseA", case["materials"]["PhaseA"]),
            material_record("PhaseB", case["materials"]["PhaseB"]),
        ],
        "Simulation": {
            "timeStepSize": 0.005,
            "maxIter": 5,
            "maxIterVel": 5,
            "velocityUpdateMethod": 0,
            "contactTolerance": 0.05,
            "contactStiffnessRigidBody": 1.0,
            "contactStiffnessParticleRigidBody": 100.0,
        },
        "RigidBodies": [{
            "id": 1,
            "geometryFile": str(model),
            "translation": [0.0, 1.0, 0.0],
            "rotationAxis": [1.0, 0.0, 0.0],
            "rotationAngle": 0.0,
            "scale": [4.0, 2.0, 2.0],
            "color": [0.5, 0.5, 0.5, 1.0],
            "isDynamic": False,
            "restitution": 0.2,
            "friction": 0.05,
            "collisionObjectType": 2,
            "collisionObjectScale": [4.0, 2.0, 2.0],
            "testMesh": 1,
            "isWall": True,
            "invertSDF": True,
            "mapInvert": True,
            "mapThickness": 0.0,
            "mapResolution": [32, 20, 20],
        }],
        "FluidBlocks": [
            {
                "id": block["id"],
                "denseMode": 0,
                "start": block["start"],
                "end": block["end"],
                "initialVelocity": block.get("initialVelocity", [0.0, 0.0, 0.0]),
            }
            for block in case["blocks"]
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scene, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "case": args.case,
        "title": case["title"],
        "gravity": case["gravity"],
        "materials": case["materials"],
        "blocks": len(case["blocks"]),
        "particle_radius": defaults["particle_radius"],
        "stop_at": defaults["stop_at"],
        "scene": str(args.output),
    }, indent=2))

if __name__ == "__main__":
    main()
