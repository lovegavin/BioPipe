"""AdaBoost regressor."""
from __future__ import annotations

from ._ml_common import _RegressionBase


class AdaBoostRegressorStep(_RegressionBase):
    name = "ada_boost_regressor"
    title = "AdaBoost regressor"
    extra_properties = {
        "n_estimators": {"type": "integer", "minimum": 1, "default": 50},
        "learning_rate": {"type": "number", "exclusiveMinimum": 0, "default": 1.0},
        "loss": {"type": "string", "enum": ["linear", "square", "exponential"], "default": "linear"},
    }

    def _build_model(self, params, random_state):
        from sklearn.ensemble import AdaBoostRegressor
        return AdaBoostRegressor(
            n_estimators=int(params.get("n_estimators", 50)),
            learning_rate=float(params.get("learning_rate", 1.0)),
            loss=params.get("loss", "linear"),
            random_state=random_state,
        )
