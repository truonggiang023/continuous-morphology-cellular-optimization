"""Postprocess a monotonic compression history in mm, N, tonne units."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid, trapezoid
from scipy.signal import find_peaks


def responses(curve, *, H0_mm, W0_mm, D0_mm, mass_tonne, min_densification_strain=.05):
    dimensions = np.array([H0_mm, W0_mm, D0_mm, mass_tonne], dtype=float)
    if not np.isfinite(dimensions).all() or (dimensions <= 0).any():
        raise ValueError("H0, W0, D0 and specimen mass must be finite and positive")
    if not 0 < min_densification_strain < 1:
        raise ValueError("min_densification_strain must be between zero and one")
    raw = curve[["U2_mm", "RF2_N"]].to_numpy(dtype=float)
    if len(raw) < 5 or not np.isfinite(raw).all():
        raise ValueError("Need at least five finite compression samples")
    if "time" in curve:
        time = curve.time.to_numpy(dtype=float)
        if not np.isfinite(time).all() or (np.diff(time) <= 0).any():
            raise ValueError("History times must be finite and strictly increasing")
    u, force = np.abs(raw[:, 0]), np.abs(raw[:, 1])
    if not np.isclose(u[0], 0, atol=1e-10) or not np.isclose(force[0], 0, atol=1e-8):
        raise ValueError("History must start at unloaded zero displacement; remove preload explicitly")
    if (np.diff(u) <= 0).any():
        raise ValueError("Compression displacement must increase strictly; review holds/unloading before processing")
    strain = u / H0_mm
    if strain[-1] >= 1:
        raise ValueError("Nominal compression strain must remain below one")
    stress = force / (W0_mm * D0_mm)  # N/mm2 = MPa
    energy_Nmm = cumulative_trapezoid(force, u, initial=0)
    integral_stress = cumulative_trapezoid(stress, strain, initial=0)
    eta = np.full(len(stress), np.nan)
    np.divide(integral_stress, stress, out=eta, where=stress > 0)
    candidates = np.flatnonzero((strain >= min_densification_strain) & np.isfinite(eta))
    if not len(candidates):
        raise ValueError("No positive-stress samples in the densification search interval")
    d = int(candidates[np.argmax(eta[candidates])])
    status = "ok"
    if d == len(strain) - 1:
        status = "maximum_at_end_review_required"
    elif d == candidates[0]:
        status = "maximum_at_search_start_review_required"
    mass_kg = mass_tonne * 1000
    EA_d = energy_Nmm[d] * .001  # N mm -> J
    PCF = float(force[:d+1].max())
    MCF = float(energy_Nmm[d] / u[d])
    # First sampled local maximum, no smoothing/prominence assumption.
    peaks, _ = find_peaks(force[:d+1])
    first_peak = float(force[peaks[0]]) if len(peaks) else None
    EA_60 = None
    if strain[-1] >= .6:
        endpoint = .6 * H0_mm
        inside = u < endpoint
        grid = np.append(u[inside], endpoint)
        loads = np.append(force[inside], np.interp(endpoint, u, force))
        EA_60 = float(trapezoid(loads, grid) * .001)
    result = {"epsilon_d": float(strain[d]), "densification_status": status,
              "EA_d_J": float(EA_d), "SEA_d_J_kg": float(EA_d / mass_kg),
              "EA_60_J": EA_60, "SEA_60_J_kg": None if EA_60 is None else EA_60 / mass_kg,
              "PCF_preD_N": PCF, "first_peak_force_N": first_peak,
              "MCF_preD_N": MCF, "CFE_preD": None if PCF == 0 else MCF / PCF,
              "plateau_stress_MPa": float(integral_stress[d] / strain[d]),
              "mass_kg": float(mass_kg), "max_strain": float(strain[-1])}
    processed = pd.DataFrame({"displacement_mm": u, "force_N": force, "strain": strain,
                              "stress_MPa": stress, "EA_J": energy_Nmm * .001,
                              "energy_efficiency": eta})
    return result, processed


def process_manifest(manifest, output, min_densification_strain=.05):
    """Fail explicitly on corrupt histories; keep failed/unreviewed FEM out of training."""
    path = Path(manifest).resolve()
    frame = pd.read_csv(path)
    required = ["design_id", "dataset", "r_L", "t", "lambda_m", "curve_csv", "qa_accepted",
                "H0_mm", "W0_mm", "D0_mm", "mass_tonne"]
    if not set(required) <= set(frame):
        raise ValueError(f"Missing manifest columns: {sorted(set(required) - set(frame))}")
    if frame.design_id.isna().any() or frame.design_id.duplicated().any():
        raise ValueError("Manifest design_id must be complete and unique")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    results = []
    import hashlib
    provenance = []
    for index, row in frame.iterrows():
        curve_path = Path(str(row.curve_csv))
        if not curve_path.is_absolute():
            curve_path = path.parent / curve_path
        result, processed = responses(pd.read_csv(curve_path), **{k: row[k] for k in
            ("H0_mm", "W0_mm", "D0_mm", "mass_tonne")}, min_densification_strain=min_densification_strain)
        processed.to_csv(output / f"curve_{index:05d}.csv", index=False)
        results.append(result)
        provenance.append({"design_id": str(row.design_id), "curve_sha256": hashlib.sha256(curve_path.read_bytes()).hexdigest()})
    merged = pd.concat([frame.reset_index(drop=True), pd.DataFrame(results)], axis=1)
    if merged.columns.duplicated().any():
        raise ValueError("Manifest already contains response columns; use original metadata manifest")
    merged.to_csv(output / "fem_responses.csv", index=False)
    (output / "postprocessing.json").write_text(json.dumps({"manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "min_densification_strain": min_densification_strain, "smoothing": "none", "curves": provenance,
        "units": "mm, N, tonne; reported energy J and SEA J/kg", "version": 1}, indent=2))
    return merged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--min-densification-strain", type=float, default=.05)
    args = parser.parse_args()
    process_manifest(args.manifest, args.output, args.min_densification_strain)
