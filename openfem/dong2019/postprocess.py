#!/usr/bin/env python3
"""Post-process the Stage-1 OpenCourant Dong validation run.

The script is intentionally defensive because th_to_csv column labels can vary by
OpenCourant release. It extracts a nominal stress-strain curve only when an
unambiguous top rigid-wall Y force and top-master Y displacement are present.
"""
from __future__ import annotations
import csv, json, re, sys
from pathlib import Path

AREA=76.0*25.0
HEIGHT=48.0
TARGETS={"plateau_exp_MPa":0.28,"plateau_fe_MPa":0.31,"densification_exp":0.58}

def norm(s:str)->str:
    return re.sub(r"[^A-Z0-9]+","_",s.upper()).strip("_")

def main():
    case=Path(sys.argv[1] if len(sys.argv)>1 else "openfem/dong2019/generated")
    csvs=sorted(case.glob("*T*.csv"))
    report={"csv_files":[p.name for p in csvs],"targets":TARGETS,"status":"history CSV not found"}
    if not csvs:
        (case/"validation_summary.json").write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
        return 0

    p=csvs[0]
    with p.open(newline="",errors="replace") as f:
        rd=csv.reader(f); headers=next(rd); rows=[]
        for r in rd:
            try: rows.append([float(x) for x in r])
            except Exception: pass
    nh=[norm(h) for h in headers]
    report.update({"history_csv":p.name,"headers":headers,"samples":len(rows),"status":"headers inventoried"})

    def candidates(tokens):
        return [i for i,h in enumerate(nh) if all(t in h for t in tokens)]
    fy=sorted(set(candidates(["RWALL","2","FY"])+candidates(["RWALL","2","FORCE","Y"])))
    dy=sorted(set(candidates(["NODE","DISP","Y"])+candidates(["NODE","DY"])))
    report["force_y_candidates"]=[headers[i] for i in fy]
    report["disp_y_candidates"]=[headers[i] for i in dy]

    if len(fy)==1 and len(dy)==1 and rows:
        curve=[]
        for r in rows:
            strain=abs(r[dy[0]])/HEIGHT
            # kg-mm-ms force unit = kN; kN*1000/mm^2 = MPa.
            stress=abs(r[fy[0]])*1000.0/AREA
            curve.append((strain,stress))
        with (case/"nominal_stress_strain.csv").open("w",newline="") as f:
            w=csv.writer(f); w.writerow(["nominal_strain","nominal_stress_MPa"]); w.writerows(curve)
        plateau=[s for e,s in curve if 0.05<=e<=0.55]
        if plateau:
            report["provisional_plateau_mean_MPa"]=sum(plateau)/len(plateau)
            report["error_vs_exp_plateau_pct"]=100*(report["provisional_plateau_mean_MPa"]-0.28)/0.28
        report["status"]="nominal curve extracted; densification requires energy-efficiency calculation/check"
    else:
        report["status"]="could not uniquely identify rigid-wall force/displacement columns; inspect headers before mapping"

    (case/"validation_summary.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
