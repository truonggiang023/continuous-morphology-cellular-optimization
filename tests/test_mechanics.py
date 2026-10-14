import numpy as np
import pandas as pd
import pytest
from cmco.mechanics import responses, process_manifest
from cmco.study import generate_doe


def compression_curve():
    e = np.linspace(0, .8, 81)
    f = np.where(e < .1, 1000 * e, np.where(e <= .5, 100., 100 + 4000 * (e - .5)))
    return pd.DataFrame({'time': e, 'U2_mm': -10 * e, 'RF2_N': -f})


def test_analytical_energy_units_and_densification():
    r, processed = responses(compression_curve(), H0_mm=10, W0_mm=10, D0_mm=10, mass_tonne=1e-6)
    assert r['densification_status'] == 'ok'
    assert r['epsilon_d'] == pytest.approx(.5)
    assert r['EA_d_J'] == pytest.approx(.45)
    assert r['SEA_d_J_kg'] == pytest.approx(450)
    assert r['SEA_60_J_kg'] == pytest.approx(750)
    assert r['PCF_preD_N'] == pytest.approx(100)
    assert r['MCF_preD_N'] == pytest.approx(90)
    assert r['plateau_stress_MPa'] == pytest.approx(.9)
    assert r['CFE_preD'] == pytest.approx(.9)
    assert processed.stress_MPa.iloc[10] == pytest.approx(1)


def test_insufficient_compression_is_flagged_not_extrapolated():
    curve = compression_curve().iloc[:41]
    r, _ = responses(curve, H0_mm=10, W0_mm=10, D0_mm=10, mass_tonne=1e-6)
    assert r['densification_status'] == 'maximum_at_end_review_required'
    assert r['SEA_60_J_kg'] is None
    with pytest.raises(ValueError, match='increase strictly'):
        responses(pd.concat([curve, curve.iloc[-1:]]).drop(columns='time'), H0_mm=10, W0_mm=10, D0_mm=10, mass_tonne=1e-6)


def test_doe_separates_controls_and_lhs(tmp_path):
    a, b = generate_doe(tmp_path / 'doe')
    assert len(a) == 21 and len(b) == 315
    assert a.t.isna().all()  # Must be solved for constant density, never assumed.
    assert list(a.lambda_m[[0, 10, 20]]) == [-1, 0, 1]
    lhs = b[b.sampling == 'LHS']
    for key, lo, hi in [('r_L', .4, .6), ('t', .3, .6), ('lambda_m', -1, 1)]:
        assert lhs[key].between(lo, hi).all()
        bins = np.floor((lhs[key] - lo) / (hi - lo) * 300).astype(int)
        assert len(set(bins)) == 300
    assert not b.qa_accepted.any()


def test_postprocess_preserves_manifest_and_provenance(tmp_path):
    compression_curve().to_csv(tmp_path / 'history.csv', index=False)
    pd.DataFrame([dict(design_id='B0001', dataset='B', r_L=.5, t=.45, lambda_m=0,
        curve_csv='history.csv', qa_accepted=0, H0_mm=10, W0_mm=10, D0_mm=10, mass_tonne=1e-6)]).to_csv(
        tmp_path / 'manifest.csv', index=False)
    result = process_manifest(tmp_path / 'manifest.csv', tmp_path / 'responses')
    assert result.qa_accepted.iloc[0] == 0  # Numerical integration is not FEM QA approval.
    assert result.SEA_60_J_kg.iloc[0] == pytest.approx(750)
    assert (tmp_path / 'responses' / 'postprocessing.json').exists()
