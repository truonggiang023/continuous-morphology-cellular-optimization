"""Standalone diagnostic figures; labels retain configured response units."""
import numpy as np
import pandas as pd


def plot_run(output, config):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for objective in config['objectives']:
        name = objective['name']
        importance = pd.read_csv(output / f'importance_{name}.csv').sort_values('mean_abs_shap')
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.barh(importance.feature, importance.mean_abs_shap)
        ax.set_xlabel(f'Mean absolute SHAP ({objective.get("unit", "response units")})')
        ax.set_title(name)
        fig.tight_layout()
        fig.savefig(output / f'shap_importance_{name}.png', dpi=200)
        plt.close(fig)
        interaction_file = output / f'shap_interactions_{name}.npz'
        if interaction_file.exists():
            content = np.load(interaction_file)
            features = list(content['features'])
            if 'lambda_m' in features:
                holdout = pd.read_csv(output / 'holdout_predictions.csv').set_index('source_row')
                sample = holdout.loc[content['source_rows']]
                i = features.index('lambda_m')
                for j, feature in enumerate(features):
                    if i == j:
                        continue
                    fig, ax = plt.subplots(figsize=(6, 4))
                    scatter = ax.scatter(sample.lambda_m, content['values'][:, i, j], c=sample[feature], cmap='viridis')
                    fig.colorbar(scatter, ax=ax, label=feature)
                    ax.set_xlabel('lambda_m')
                    ax.set_ylabel(f'SHAP interaction ({objective.get("unit", "response units")})')
                    ax.set_title(f'{name}: lambda_m × {feature}')
                    fig.tight_layout()
                    fig.savefig(output / f'interaction_{name}_lambda_m_{feature}.png', dpi=200)
                    plt.close(fig)
    if len(config['objectives']) == 2:
        a, b = config['objectives']
        pareto = pd.read_csv(output / 'pareto_predictions.csv')
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.scatter(pareto[f'predicted_{a["name"]}'], pareto[f'predicted_{b["name"]}'], s=15)
        ax.set_xlabel(a['name'])
        ax.set_ylabel(b['name'])
        ax.set_title('Surrogate Pareto predictions — pending FEM validation')
        fig.tight_layout()
        fig.savefig(output / 'pareto_predictions.png', dpi=200)
        plt.close(fig)
