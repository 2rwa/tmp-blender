from __future__ import annotations
import argparse, json, re
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent

def main():
    p = argparse.ArgumentParser()
    p.add_argument("case")
    p.add_argument("upstream_xml", type=Path)
    p.add_argument("output_xml", type=Path)
    p.add_argument("--metadata", type=Path)
    a = p.parse_args()

    cfg = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    spec = cfg["cases"].get(a.case)
    if spec is None:
        raise SystemExit(f"unknown case: {a.case}")
    if not a.upstream_xml.is_file():
        raise SystemExit(f"missing upstream XML: {a.upstream_xml}")

    tree = ET.parse(a.upstream_xml)
    root = tree.getroot()

    body = root.find(".//deformstrucbody")
    if body is None:
        raise SystemExit("deformstrucbody missing")
    frac = body.find("fracture")
    gc = body.find("Gc")
    if frac is None or gc is None:
        raise SystemExit("fracture/Gc missing")
    frac.set("value", "1")
    gc.set("value", f"{float(spec['Gc']):.10g}")

    expr = root.find(".//mathexpressions/userexpression[@id='2']/locals")
    if expr is None:
        raise SystemExit("impact expression locals missing")
    locals_value = expr.get("value", "")
    if not re.search(r"maxv=[^;]+", locals_value):
        raise SystemExit(f"maxv not found in locals: {locals_value}")
    expr.set("value", re.sub(r"maxv=[^;]+", f"maxv={float(spec['maxv']):.10g}", locals_value))

    a.output_xml.parent.mkdir(parents=True, exist_ok=True)
    tree.write(a.output_xml, encoding="UTF-8", xml_declaration=True)

    meta = {
        "case": a.case,
        "title": spec["title"],
        "description": spec["description"],
        "maxv": float(spec["maxv"]),
        "Gc": float(spec["Gc"]),
        "fracture": True,
        "upstream_example": cfg["upstream_example"],
        "exploratory": True
    }
    if a.metadata:
        a.metadata.parent.mkdir(parents=True, exist_ok=True)
        a.metadata.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))

if __name__ == "__main__":
    main()
