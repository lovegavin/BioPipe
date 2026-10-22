"""Lasso (L1-penalized) linear regression."""
from __future__ import annotations
from ._ml_common import _RegressionBase


class LassoRegressionStep(_RegressionBase):
    name = "lasso_regression"
    title = "Lasso regression"
    extra_properties = {
        "alpha": {"type": "number", "exclusiveMinimum": 0,
                    "default": 0.001},
    }

    def _build_model(self, params, random_state):
        from sklearn.linear_model import Lasso
        return Lasso(alpha=float(params.get("alpha", 0.001)),
                     max_iter=10000)
