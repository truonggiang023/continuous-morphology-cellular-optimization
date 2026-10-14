"""SYNTHETIC mechanics curves for software testing, never research/FEA evidence."""
import argparse
from pathlib import Path
import numpy as np
from cmco.study import generate_doe


def generate(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    _, frame = generate_doe(output / 'plans', n=40)
    (output / 'curves').mkdir()
    e = np.linspace(0, .8, 161)
    for i, row in frame.iterrows():
        # Deliberately artificial relationships, not constitutive or geometry laws.
        plateau = 1000 * row.t * (1 + .1 * row.lambda_m + .1 * row.r_L)
        d = .48 + .04 * row.lambda_m
        f = np.where(e < .1, plateau * e / .1,
                     np.where(e <= d, plateau, plateau * (1 + 40 * (e - d))))
        import pandas as pd
        relative = f'curves/{row.design_id}.csv'
        pd.DataFrame({'time': e, 'U2_mm': -10 * e, 'RF2_N': -f}).to_csv(output / relative, index=False)
        frame.loc[i, 'curve_csv'] = relative
    frame['H0_mm'], frame['W0_mm'], frame['D0_mm'] = 10., 10., 10.
    frame['mass_tonne'] = 1e-6
    frame['qa_accepted'] = 1
    frame['data_origin'] = 'SYNTHETIC_SOFTWARE_TEST_NOT_FEM'
    frame['notes'] = 'Artificial inputs and curves; QA flag for software exercise only'
    frame.to_csv(output / 'synthetic_manifest.csv', index=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    generate(parser.parse_args().output)
