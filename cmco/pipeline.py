"""CSV-based research workflow. All objectives are predicted by FEM surrogates."""
import argparse
import json
import re
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from .models import benchmark, explain


def load_data(csv, config):
    features = config["features"]
    objectives = config["objectives"]
    names = [x["name"] for x in features]
    targets = [x["name"] for x in objectives]
    if not names or not targets or len(set(names + targets)) != len(names + targets):
        raise ValueError("Feature and objective names must be nonempty and unique")
    if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) for name in names + targets):
        raise ValueError("Use identifier-style column names: letters, digits and underscores")
    for f in features:
        if not np.isfinite([f["lower"], f["upper"]]).all() or f["lower"] >= f["upper"]:
            raise ValueError(f"Invalid bounds: {f['name']}")
    if any(o["direction"] not in ("min", "max") for o in objectives):
        raise ValueError("Objective direction must be min or max")
    frame = pd.read_csv(csv)
    for column, value in config.get("filters", {}).items():
        frame = frame.loc[frame[column] == value]
    values = frame[names + targets].to_numpy(dtype=float)
    if len(frame) < 10 or not np.isfinite(values).all():
        raise ValueError("Need at least 10 complete, finite FEM rows")
    for f in features:
        if not frame[f["name"]].between(f["lower"], f["upper"]).all():
            raise ValueError(f"FEM values outside design bounds: {f['name']}")
    if frame.duplicated(names).any() and not config.get("group_column"):
        raise ValueError("Repeated designs require group_column to avoid train/test leakage")
    group = config.get("group_column")
    if group:
        if frame[group].isna().any():
            raise ValueError("Group labels must be complete")
        if (frame.groupby(names, dropna=False)[group].nunique() > 1).any():
            raise ValueError("Identical designs must belong to the same group")
    return frame, names, targets


def run(csv, config_path, output):
    config = json.loads(Path(config_path).read_text())
    frame, names, targets = load_data(csv, config)
    seed = config.get("seed", 42)
    test_size = config.get("test_size", 0.2)
    indices = np.arange(len(frame))
    if config.get("group_column"):
        train, test = next(GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=seed).split(
            frame, groups=frame[config["group_column"]]))
    else:
        train, test = train_test_split(indices, test_size=test_size, random_state=seed)
    if len(test) < 2:
        raise ValueError("Holdout must contain at least two samples")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    models, metrics, model_names = {}, {}, {}
    predictions = frame.iloc[test][names + targets].copy()
    for target in targets:
        groups = frame.iloc[train][config["group_column"]] if config.get("group_column") else None
        model, model_name, comparison = benchmark(frame.iloc[train][names], frame.iloc[train][target], config, groups)
        comparison.to_csv(output / f"cv_{target}.csv", index=False)
        model_names[target] = model_name
        predicted = model.predict(frame.iloc[test][names])
        actual = frame.iloc[test][target]
        metrics[target] = {"mae": float(mean_absolute_error(actual, predicted)),
                           "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
                           "r2": float(r2_score(actual, predicted))}
        predictions[f"predicted_{target}"] = predicted
        sample = frame.iloc[test][names].iloc[:config.get("shap_samples", 100)]
        explain(model, model_name, frame.iloc[train][names], sample, target, output, seed)
        models[target] = model
    predictions.to_csv(output / "holdout_predictions.csv", index_label="source_row")
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2))
    pd.DataFrame({"source_row": frame.index, "split": np.where(np.isin(indices, train), "train", "test")}).to_csv(
        output / "split.csv", index=False)
    joblib.dump({"models": models, "model_names": model_names, "config": config, "features": names}, output / "surrogates.joblib")
    optimize(models, names, config, output, frame.iloc[train][names])
    if config.get("plots", True):
        from .plots import plot_run
        plot_run(output, config)
    import hashlib
    from importlib.metadata import version
    (output / "run.json").write_text(json.dumps({"config": config, "data_sha256": hashlib.sha256(Path(csv).read_bytes()).hexdigest(),
        "rows": len(frame), "data_origins": frame["data_origin"].value_counts().to_dict() if "data_origin" in frame else {"unspecified": len(frame)}, "train_rows": len(train), "test_rows": len(test),
        "model_names": model_names,
        "selection": "train-only CV; holdout is not used for hyperparameter or model selection",
        "versions": {p: version(p) for p in ["numpy", "pandas", "scikit-learn", "shap", "pymoo", "xgboost"]},
        "warning": "Pareto outputs are surrogate predictions; validate selected designs with independent FEM. Models use training split only."}, indent=2))
    return metrics


def optimize(models, names, config, output, training=None):
    from pymoo.core.problem import Problem
    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.optimize import minimize
    objectives = config["objectives"]
    class SurrogateProblem(Problem):
        def __init__(self):
            super().__init__(n_var=len(names), n_obj=len(objectives),
                xl=[f["lower"] for f in config["features"]], xu=[f["upper"] for f in config["features"]])
        def _evaluate(self, x, out, *args, **kwargs):
            data = pd.DataFrame(x, columns=names)
            out["F"] = np.column_stack([models[o["name"]].predict(data) * (1 if o["direction"] == "min" else -1) for o in objectives])
    result = minimize(SurrogateProblem(), NSGA2(pop_size=config.get("population", 100)),
                      ("n_gen", config.get("generations", 100)), seed=config.get("seed", 42), verbose=False)
    if result.X is None:
        raise RuntimeError("NSGA-II returned no solutions")
    data = pd.DataFrame(np.atleast_2d(result.X), columns=names)
    for o in objectives:
        data[f"predicted_{o['name']}"] = models[o["name"]].predict(data[names])
    if training is not None:
        from scipy.spatial.distance import cdist
        scale = np.array([f["upper"] - f["lower"] for f in config["features"]])
        data["nearest_training_distance_scaled"] = cdist(data[names].to_numpy() / scale,
                                                         training.to_numpy() / scale).min(axis=1)
        data["outside_training_box"] = ((data[names] < training.min()) | (data[names] > training.max())).any(axis=1)
    data.to_csv(output / "pareto_predictions.csv", index=False)
    scores = np.column_stack([data[f"predicted_{o['name']}"] * (1 if o["direction"] == "min" else -1)
                              for o in objectives])
    span = np.ptp(scores, axis=0)
    normalized = (scores - scores.min(axis=0)) / np.where(span > 0, span, 1)
    selections = [(f"best_{o['name']}", int(np.argmin(scores[:, i]))) for i, o in enumerate(objectives)]
    selections.append(("closest_to_normalized_ideal", int(np.argmin(np.linalg.norm(normalized, axis=1)))))
    selected = pd.DataFrame([dict(data.iloc[i], selection=label, pareto_row=i, verification_status="pending_abaqus")
                             for label, i in selections])
    selected.to_csv(output / "abaqus_verification_candidates.csv", index=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True, help="New directory; existing results are never overwritten")
    args = parser.parse_args()
    print(json.dumps(run(args.data, args.config, args.output), indent=2))


if __name__ == "__main__":
    main()
