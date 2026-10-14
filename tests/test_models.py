import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
from cmco.pipeline import run, load_data
from cmco.models import benchmark


def test_study_models_interactions_and_group_isolation(tmp_path):
    rng = np.random.default_rng(18)
    n = 60
    x = rng.uniform(-1, 1, n)
    r = rng.uniform(.4, .6, n)
    t = rng.uniform(.3, .6, n)
    frame = pd.DataFrame(dict(design_id=[f'B{i}' for i in range(n)], dataset='B', qa_accepted=1,
        densification_status='ok', r_L=r, t=t, lambda_m=x,
        SEA_60_J_kg=1000*(1+x*.2)*t, PCF_preD_N=10000*t*r*(1+.1*x)))
    # Replicate designs inside groups: no group may cross train/test boundaries.
    frame = pd.concat([frame, frame], ignore_index=True)
    config = json.loads(Path('configs/alsi10mg.json').read_text())
    config.update(trees=10, population=12, generations=3, cv_folds=3, shap_samples=5,
        model_grids={'xgboost': {'max_depth': [2], 'learning_rate': [.1]},
                     'random_forest': {'max_depth': [4]},
                     'svr': {'regressor__svr__C': [10.]}})
    config_path = tmp_path / 'config.json'
    config_path.write_text(json.dumps(config))
    csv = tmp_path / 'data.csv'
    frame.to_csv(csv, index=False)
    output = tmp_path / 'results'
    run(csv, config_path, output)
    split = pd.read_csv(output / 'split.csv')
    assert split.join(frame.design_id, on='source_row').groupby('design_id').split.nunique().max() == 1
    cv = pd.read_csv(output / 'cv_SEA_60_J_kg.csv')
    assert set(cv.model) == {'xgboost', 'random_forest', 'svr'}
    values = np.load(output / 'shap_interactions_SEA_60_J_kg.npz')['values']
    assert values.shape == (5, 3, 3)
    shap_values = pd.read_csv(output / 'shap_SEA_60_J_kg.csv').drop(columns='source_row').to_numpy()
    assert np.allclose(values.sum(axis=2), shap_values, atol=1e-3)
    baseline = pd.read_csv(output / 'shap_baseline_SEA_60_J_kg.csv')
    assert np.allclose(shap_values.sum(axis=1) + baseline.base_value, baseline.prediction, atol=1e-3)
    assert pd.read_csv(output / 'abaqus_verification_candidates.csv').verification_status.eq('pending_abaqus').all()
    assert json.loads((output / 'run.json').read_text())['model_names']['PCF_preD_N'] == 'xgboost'


def test_filters_preserve_original_source_rows(tmp_path):
    config = json.loads(Path('examples/config.json').read_text())
    config['filters'] = {'dataset': 'B', 'qa_accepted': 1}
    frame = pd.DataFrame(dict(morphology_parameter=np.linspace(0, 1, 20), relative_density=.2,
                             SEA=1, peak_force=2, dataset=['A']*5 + ['B']*15, qa_accepted=1))
    frame.to_csv(tmp_path / 'data.csv', index=False)
    selected, _, _ = load_data(tmp_path / 'data.csv', config)
    assert list(selected.index) == list(range(5, 20))


def test_abaqus_adapter_time_alignment_without_solver():
    spec = importlib.util.spec_from_file_location('export', 'scripts/export_abaqus_history.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    history = lambda values: SimpleNamespace(data=values)
    region = SimpleNamespace(historyOutputs={'U2': history([(0, 0), (1, -2)]),
                                             'RF2': history([(0, 0), (1, 10)])})
    step = SimpleNamespace(historyRegions={'RP': region})
    assert module.synchronized_history(step, 'RP', 'RP') == [(0, 0, 0), (1, -2, 10)]


def test_svr_shap_preserves_original_response_units(tmp_path):
    from cmco.models import explain
    rng = np.random.default_rng(1)
    X = pd.DataFrame(rng.uniform(0, 1, (20, 3)), columns=['r_L', 't', 'lambda_m'])
    y = 1000 + 200 * X.r_L - 50 * X.t
    model, name, _ = benchmark(X, y, {'primary_model': 'svr', 'cv_folds': 2,
        'model_grids': {'svr': {'regressor__svr__C': [10.]}}})
    explain(model, name, X, X.iloc[:2], 'response', tmp_path, 42)
    values = pd.read_csv(tmp_path / 'shap_response.csv').drop(columns='source_row').sum(axis=1)
    baseline = pd.read_csv(tmp_path / 'shap_baseline_response.csv')
    assert np.allclose(values + baseline.base_value, model.predict(X.iloc[:2]), atol=1e-6)
    assert not (tmp_path / 'shap_interactions_response.npz').exists()
