"""Ridge (L2-penalized) linear regression."""
from __future__ import annotations
from ._ml_common import _RegressionBase


class RidgeRegressionStep(_RegressionBase):
    name = "ridge_regression"
    title = "Ridge regression"
    extra_properties = {
        "alpha": {"type": "number", "exclusiveMinimum": 0,
                    "default": 1.0},
    }

    def _build_model(self, params, random_state):
        from sklearn.linear_model import Ridge
        return Ridge(alpha=float(params.get("alpha", 1.0)))
