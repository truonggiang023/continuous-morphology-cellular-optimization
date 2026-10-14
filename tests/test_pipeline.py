import json
import numpy as np
import pandas as pd
import pytest
from cmco.pipeline import run, load_data


def test_full_pipeline(tmp_path):
    config = json.loads(open('examples/config.json').read())
    config.update(trees=10, population=12, generations=3)
    config_path = tmp_path / 'config.json'
    config_path.write_text(json.dumps(config))
    rng = np.random.default_rng(3)
    x = rng.uniform(0, 1, 60)
    r = rng.uniform(.1, .4, 60)
    data = tmp_path / 'fem.csv'
    pd.DataFrame(dict(morphology_parameter=x, relative_density=r, SEA=x+r, peak_force=r-x)).to_csv(data, index=False)
    output = tmp_path / 'results'
    metrics = run(data, config_path, output)
    assert set(metrics) == {'SEA', 'peak_force'}
    assert all(np.isfinite(m['rmse']) for m in metrics.values())
    pareto = pd.read_csv(output / 'pareto_predictions.csv')
    assert len(pareto) > 0
    assert pareto.relative_density.between(.1, .4).all()
    assert pareto.morphology_parameter.between(0, 1).all()
    # Check nondominance after converting maximization to minimization.
    scores = pareto[['predicted_SEA', 'predicted_peak_force']].to_numpy() * [-1, 1]
    for row in scores:
        assert not np.any(np.all(scores <= row, axis=1) & np.any(scores < row, axis=1))
    assert pd.read_csv(output / 'shap_SEA.csv').shape[0] == 12
    split = pd.read_csv(output / 'split.csv')
    assert (split.split == 'test').sum() == 12
    with pytest.raises(FileExistsError):
        run(data, config_path, output)


def test_repeated_designs_need_groups(tmp_path):
    config = json.loads(open('examples/config.json').read())
    data = tmp_path / 'duplicates.csv'
    pd.DataFrame(dict(morphology_parameter=[.5]*10, relative_density=[.2]*10,
                      SEA=[1]*10, peak_force=[2]*10)).to_csv(data, index=False)
    with pytest.raises(ValueError, match='group_column'):
        load_data(data, config)
