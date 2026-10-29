"""Linear regressor trained with stochastic gradient descent."""
from __future__ import annotations

from ._ml_common import _RegressionBase


class SgdRegressorStep(_RegressionBase):
    name = "sgd_regressor"
    title = "SGD regressor"
    extra_properties = {
        "loss": {"type": "string", "enum": ["squared_error", "huber", "epsilon_insensitive"], "default": "squared_error"},
        "penalty": {"type": "string", "enum": ["l2", "l1", "elasticnet"], "default": "l2"},
        "alpha": {"type": "number", "exclusiveMinimum": 0, "default": 0.0001},
        "max_iter": {"type": "integer", "minimum": 1, "default": 1000},
    }

    def _build_model(self, params, random_state):
        from sklearn.linear_model import SGDRegressor
        return SGDRegressor(
            loss=params.get("loss", "squared_error"),
            penalty=params.get("penalty", "l2"),
            alpha=float(params.get("alpha", 1e-4)),
            max_iter=int(params.get("max_iter", 1000)),
            random_state=random_state,
        )
