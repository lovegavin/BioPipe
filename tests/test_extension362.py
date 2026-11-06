import inspect

import numpy as np

from src.task.step.steps import limma_de


def test_prior_estimation_works_without_private_gamma_helpers():
    s2 = np.array([0.1, 0.5, 2.0, 8.0, 0.2, 4.0])
    df_prior, s2_prior = limma_de._prior(s2, df=4, prior_df=None)
    assert np.isfinite(df_prior) and 0 < df_prior <= 2_000_000
    assert np.isfinite(s2_prior) and s2_prior > 0


def test_limma_uses_only_public_scipy_special_functions():
    source = inspect.getsource(limma_de)
    assert "stats.distributions.gamma._" not in source
    assert "_digamma" not in source
