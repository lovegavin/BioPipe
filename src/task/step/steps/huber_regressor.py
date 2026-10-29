"""Robust Huber regression."""
from __future__ import annotations

from ._ml_common import _RegressionBase


class HuberRegressorStep(_RegressionBase):
    name = "huber_regressor"
    title = "Huber regressor"
    extra_properties = {
        "epsilon": {"type": "number", "exclusiveMinimum": 1, "default": 1.35},
        "alpha": {"type": "number", "exclusiveMinimum": 0, "default": 0.0001},
        "max_iter": {"type": "integer", "minimum": 1, "default": 100},
    }

    def _build_model(self, params, random_state):
        from sklearn.linear_model import HuberRegressor
        return HuberRegressor(
            epsilon=float(params.get("epsilon", 1.35)),
            alpha=float(params.get("alpha", 1e-4)),
            max_iter=int(params.get("max_iter", 100)),
        )
