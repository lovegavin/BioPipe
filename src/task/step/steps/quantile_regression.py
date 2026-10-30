"""Linear quantile regression."""
from __future__ import annotations

from ._ml_common import _RegressionBase


class QuantileRegressionStep(_RegressionBase):
    name = "quantile_regression"
    title = "Quantile regression"
    extra_properties = {
        "quantile": {"type": "number", "exclusiveMinimum": 0, "exclusiveMaximum": 1, "default": 0.5},
        "alpha": {"type": "number", "minimum": 0, "default": 0.0},
        "solver": {"type": "string", "enum": ["highs", "highs-ds", "highs-ipm"], "default": "highs"},
    }

    def _build_model(self, params, random_state):
        from sklearn.linear_model import QuantileRegressor
        return QuantileRegressor(
            quantile=float(params.get("quantile", 0.5)),
            alpha=float(params.get("alpha", 0.0)),
            solver=str(params.get("solver", "highs")),
        )
