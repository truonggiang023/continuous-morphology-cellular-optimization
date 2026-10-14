"""Study-specific DOE, keeping mechanics dataset A separate from surrogate dataset B."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import qmc


FEATURES = ["r_L", "t", "lambda_m"]
LOWER = [.4, .3, -1.]
UPPER = [.6, .6, 1.]


def generate_doe(output, n=300, seed=42):
    if n < 1:
        raise ValueError("n must be positive")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    a = pd.DataFrame({"lambda_m": np.round(np.linspace(-1, 1, 21), 1)})
    a["r_L"] = .5
    # Solving t is a geometry task: fixed t would generally vary relative density.
    a["t"] = np.nan
    a["reference_t_mm"] = .45
    a["sampling"] = "controlled_morphology"
    b = pd.DataFrame(qmc.scale(qmc.LatinHypercube(3, seed=seed).random(n), LOWER, UPPER), columns=FEATURES)
    b["sampling"] = "LHS"
    anchors = pd.DataFrame([(r, t, m) for r in (.4, .6) for t in (.3, .6) for m in (-1., 0., 1.)] +
                           [(.5, .45, m) for m in (-1., 0., 1.)], columns=FEATURES)
    anchors["sampling"] = "anchor"
    b = pd.concat([b, anchors], ignore_index=True)
    for label, frame in (("A", a), ("B", b)):
        frame.insert(0, "design_id", [f"{label}{i+1:04d}" for i in range(len(frame))])
        frame.insert(1, "dataset", label)
        frame["material"] = "AlSi10Mg"
        frame["E_MPa"], frame["nu"], frame["rho_tonne_mm3"] = 69000., .30, 2.67e-9
        frame["geometry_status"] = "requires_geometry_resolution"
        frame["qa_accepted"] = 0
        for column in ("H0_mm", "W0_mm", "D0_mm", "mass_tonne", "relative_density",
                       "curve_csv", "odb_path", "mesh_id", "deformation_mode", "notes"):
            frame[column] = ""
        frame.to_csv(output / f"dataset_{label}_plan.csv", index=False)
    return a, b


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--n", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    generate_doe(args.output, args.n, args.seed)
