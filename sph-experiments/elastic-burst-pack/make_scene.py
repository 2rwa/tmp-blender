from __future__ import annotations
import argparse, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL_PATH = ROOT.parent / "elastic-pack" / "models" / "UnitBox.obj"

def elastic_params(spec):
    out = {
        "youngsModulus": float(spec["youngsModulus"]),
        "poissonsRatio": float(spec["poissonsRatio"]),
        "alpha": float(spec.get("alpha", 0.1)),
        "maxNeighbors": int(spec.get("maxNeighbors", 20)),
        "elasticityMaxIter": int(spec.get("elasticityMaxIter", 120)),
        "elasticityMaxError": float(spec.get("elasticityMaxError", 0.0001)),
    }
    for key in ("fixedBoxMin","fixedBoxMax","volumeMaxError","volumeMaxIter"):
        if key in spec:
            out[key] = spec[key]
    return out

def main():
    p = argparse.ArgumentParser()
    p.add_argument("case")
    p.add_argument("output", type=Path)
    a = p.parse_args()
    cfg = json.loads((ROOT/"cases.json").read_text())
    case = cfg["cases"].get(a.case)
    if case is None:
        raise SystemExit(f"unknown case: {a.case}")
    d = cfg["defaults"]
    e = case["elasticity"]
    model = MODEL_PATH.resolve()
    if not model.is_file():
        raise SystemExit(f"missing model: {model}")

    scene = {
      "Configuration":{
        "pause":False, "stopAt":float(d["stop_at"]),
        "timeStepSize":float(d["time_step"]), "numberOfStepsPerRenderUpdate":2,
        "particleRadius":float(d["particle_radius"]), "simulationMethod":4,
        "gravitation":case["gravity"], "cflMethod":0, "cflFactor":1.0,
        "cflMaxTimeStepSize":0.0015, "enableZSort":False,
        "boundaryHandlingMethod":2, "enableVTKExport":True,
        "enableRigidBodyExport":False, "enableRigidBodyVTKExport":False,
        "dataExportFPS":float(d["fps"]), "particleAttributes":"velocity;density",
        "DFSPH":{"minIterations":2,"maxIterations":120,"maxError":0.01,
                 "maxIterationsV":120,"maxErrorV":0.1,"enableDivergenceSolver":True}
      },
      "Materials":[{
        "id":"Fluid","density0":1000.0,"elasticityMethod":int(e["method"]),
        "viscosityMethod":1,"Standard viscosity":{"viscosity":0.01},
        e["name"]:elastic_params(e)
      }],
      "RigidBodies":[{
        "geometryFile":str(model),"translation":[0,-0.1,0],
        "rotationAxis":[1,0,0],"rotationAngle":0.0,"scale":[6,0.2,6],
        "color":[0.15,0.18,0.22,1.0],"isDynamic":False,"isWall":False,
        "mapInvert":False,"mapThickness":0.0,"mapResolution":[40,10,40]
      }],
      "FluidBlocks":[{
        "id":"Fluid","denseMode":0,"start":b["start"],"end":b["end"],
        "initialVelocity":b.get("initialVelocity",[0,0,0])
      } for b in case["blocks"]]
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(scene, indent=2)+"\n")
    print(json.dumps({"case":a.case,"blocks":len(case["blocks"]),"classification":case["classification"],"elasticity":e}, indent=2))

if __name__ == "__main__":
    main()
