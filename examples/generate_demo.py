"""Generate synthetic software-test data only: NOT FEM or research evidence."""
import sys
import numpy as np
import pandas as pd
rng = np.random.default_rng(42)
m = rng.uniform(0, 1, 120)
rho = rng.uniform(0.1, 0.4, 120)
pd.DataFrame({"morphology_parameter": m, "relative_density": rho,
              "SEA": 1000 * rho * (1 + m),
              "peak_force": 10000 * rho ** 2 * (1 + 0.3 * m)}).to_csv(sys.argv[1], index=False)
