"""Train-only model comparison and target-wise surrogate selection."""
import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GridSearchCV, GroupKFold, KFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR


def benchmark(X, y, config, groups=None):
    seed = config.get("seed", 42)
    primary = config.get("primary_model", "random_forest")
    candidates = config.get("benchmark_models", [primary])
    if primary != "best_cv" and primary not in candidates:
        raise ValueError("Primary model must appear in benchmark_models")
    folds = config.get("cv_folds", 5)
    if not 2 <= folds <= (len(np.unique(groups)) if groups is not None else len(X)):
        raise ValueError("Not enough independent training rows/groups for configured CV folds")
    splitter = GroupKFold(folds) if groups is not None else KFold(folds, shuffle=True, random_state=seed)
    searches, summary = {}, []
    for name in candidates:
        if name == "xgboost":
            from xgboost import XGBRegressor
            estimator = XGBRegressor(objective="reg:squarederror", n_estimators=config.get("trees", 200),
                                     random_state=seed, n_jobs=1, tree_method="hist")
            grid = {"max_depth": [2, 4], "learning_rate": [.05, .1]}
        elif name == "random_forest":
            estimator = RandomForestRegressor(n_estimators=config.get("trees", 200), random_state=seed, n_jobs=1)
            grid = {"max_depth": [None, 8], "min_samples_leaf": [1, 2]}
        elif name == "svr":
            # Both transforms are fitted separately inside each CV training fold.
            estimator = TransformedTargetRegressor(regressor=make_pipeline(StandardScaler(), SVR()),
                                                     transformer=StandardScaler())
            grid = {"regressor__svr__C": [1., 10., 100.], "regressor__svr__epsilon": [.05, .1]}
        else:
            raise ValueError(f"Unknown surrogate: {name}")
        grid = config.get("model_grids", {}).get(name, grid)
        search = GridSearchCV(estimator, grid, cv=splitter, scoring="neg_root_mean_squared_error",
                              n_jobs=1, error_score="raise", refit=True)
        search.fit(X, y, groups=groups)
        searches[name] = search
        for i, params in enumerate(search.cv_results_["params"]):
            summary.append({"model": name, "params": str(params),
                            "cv_rmse_mean": -float(search.cv_results_["mean_test_score"][i]),
                            "cv_rmse_std": float(search.cv_results_["std_test_score"][i])})
    selected = min(searches, key=lambda name: -searches[name].best_score_) if primary == "best_cv" else primary
    return searches[selected].best_estimator_, selected, pd.DataFrame(summary)


def explain(model, model_name, train, sample, target, output, seed):
    import shap
    if model_name in ("xgboost", "random_forest"):
        explainer = shap.TreeExplainer(model)
        explanation = explainer(sample)
        interactions = np.asarray(explainer.shap_interaction_values(sample))
        np.savez_compressed(output / f"shap_interactions_{target}.npz", values=interactions,
                            features=np.asarray(sample.columns, dtype=str), source_rows=sample.index.to_numpy())
        rows = [{"feature_1": a, "feature_2": b,
                 "mean_abs_interaction": float(np.abs(interactions[:, i, j]).mean())}
                for i, a in enumerate(sample.columns) for j, b in enumerate(sample.columns) if i < j]
        pd.DataFrame(rows).to_csv(output / f"interaction_importance_{target}.csv", index=False)
    else:
        background = train.sample(min(50, len(train)), random_state=seed)
        def predict(values):
            return model.predict(pd.DataFrame(values, columns=train.columns))
        # Exact explanation is practical for this study's three features.
        explanation = shap.Explainer(predict, background, algorithm="permutation", seed=seed)(
            sample, max_evals=max(2 * sample.shape[1] + 1, 100))
        # Tree interaction values are not defined for the SVR fallback.
    pd.DataFrame(explanation.values, columns=sample.columns, index=sample.index).to_csv(
        output / f"shap_{target}.csv", index_label="source_row")
    pd.DataFrame({"feature": sample.columns, "mean_abs_shap": np.abs(explanation.values).mean(axis=0)}).to_csv(
        output / f"importance_{target}.csv", index=False)
    pd.DataFrame({"source_row": sample.index, "base_value": np.asarray(explanation.base_values).reshape(-1),
                  "prediction": model.predict(sample)}).to_csv(output / f"shap_baseline_{target}.csv", index=False)
