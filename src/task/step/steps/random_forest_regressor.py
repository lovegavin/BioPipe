"""Random Forest regressor."""
from __future__ import annotations
from ._ml_common import _RegressionBase


class RandomForestRegressorStep(_RegressionBase):
    name = "random_forest_regressor"
    title = "Random Forest regressor"
    extra_properties = {
        "n_estimators": {"type": "integer", "minimum": 1, "default": 100},
        "max_depth": {"type": ["integer", "null"], "minimum": 1,
                       "default": None},
    }

    def _build_model(self, params, random_state):
        from sklearn.ensemble import RandomForestRegressor
        return RandomForestRegressor(
            n_estimators=int(params.get("n_estimators", 100)),
            max_depth=params.get("max_depth"),
            random_state=random_state,
        )
