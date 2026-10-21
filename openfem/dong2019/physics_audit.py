#!/usr/bin/env python3
"""Physics preflight for Dong 2019/OpenCourant validation.

Never label a run 'validated' if mass scaling, geometry or element quality
has not been checked. Accepts the existing model_report.json and engine.log.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

def audit(case: Path):
    report=json.loads((case/"model_report.json").read_text())
    geom=report["geometry"]; mesh=report["mesh"]; loading=report["loading"]
    findings=[]
    def record(name, actual, limit, ok, note):
        findings.append({"check":name,"actual":actual,"criterion":limit,
                         "pass":bool(ok),"note":note})
    mesh_area=float(geom["mesh_area_mm2"])
    geometry_area=float(geom["exact_section_area_mm2"])
    rel_error=abs(mesh_area/geometry_area-1)
    record("mesh-to-CAD area mismatch",round(rel_error*100,3),"<= 2%",rel_error <= .02,
           "Large discrepancy changes relative density and compressive response.")
    q=mesh["selected"]
    sj=float(q["min_scaled_jacobian_2d"])
    record("minimum quad scaled Jacobian",sj,">= 0.2 (provisional screening)",sj>=.2,
           "This is a screening threshold, not a universal solver criterion.")
    record("nonpositive quad corners",q["nonpositive_corners"],"0",q["nonpositive_corners"]==0,
           "Inverted corners are not allowed.")
    velocity=(float(loading["compression_strain"])*float(geom["nominal_height_mm"])/
              float(loading["step_time_ms"])) * 60000
    record("crosshead velocity, mm/min",round(velocity,3),"paper FE: 2 mm/min",
           abs(velocity-2)<0.02,
           "Accelerated runs require KE/IE and rate-independence checks.")
    starter=case/"starter.log"
    if starter.exists():
        starter_text=starter.read_text(errors="replace")
        counts=[int(m) for m in re.findall(r"(\d+) INCOMPATIBLE KINEMATIC CONDITIONS",starter_text)]
        conflicts=max(counts, default=0)
        record("incompatible kinematic constraints",conflicts,"0",conflicts==0,
               "Resolve WARNING 312 before trusting deformation or reaction loads.")
    else:
        record("starter log exists",False,"True",False,"Run Starter and save starter.log.")
    engine=case/"engine.log"
    if engine.exists():
        log=engine.read_text(errors="replace")
        mass=[float(s.replace("D","E")) for s in re.findall(
            r"DM/M=\s*([+\-\d.EeDd]+)",log)]
        err=[float(s.replace("D","E")) for s in re.findall(
            r"\bERR=\s*([+\-\d.EeDd]+)%",log)]
        if mass:
            mx=max(abs(x) for x in mass)
            record("max reported DM/M",mx,"investigate; target near zero",
                   mx <= .01,"If units are reported in percent rather than a fraction, verify solver semantics first.")
        if err:
            mx=max(abs(x) for x in err)
            record("max absolute solver ERR percent",mx,"<= 5% (screening)",mx<=5,
                   "Interpret according to the exact OpenCourant energy-error definition.")
    else:
        record("engine log exists",False,"True",False,"Run solver and retain engine.log.")
    ok=all(x["pass"] for x in findings)
    return {"status":"PASS" if ok else "NOT VALIDATED",
            "paper":"Dong et al. (2019), doi:10.1016/j.matdes.2019.108036",
            "checks":findings,
            "next_actions":["Correct meshing/geometry before material calibration.",
                            "Disable or strictly limit mass scaling and validate quasi-static energy balance.",
                            "Calibrate plateau only after reaction-force extraction and mesh convergence.",
                            "Enable ductile damage in a separate sensitivity run, not as an undocumented fit."]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--case",type=Path,default=Path("openfem/dong2019/generated"))
    args=p.parse_args()
    result=audit(args.case)
    dest=args.case/"physics_audit.json"
    dest.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    return 0 if result["status"]=="PASS" else 2

if __name__=="__main__":
    raise SystemExit(main())
