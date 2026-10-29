"""Extremely randomized trees regressor."""
from __future__ import annotations

from ._ml_common import _RegressionBase


class ExtraTreesRegressorStep(_RegressionBase):
    name = "extra_trees_regressor"
    title = "Extra Trees regressor"
    extra_properties = {
        "n_estimators": {"type": "integer", "minimum": 1, "default": 100},
        "max_depth": {"type": ["integer", "null"], "minimum": 1, "default": None},
        "min_samples_leaf": {"type": "integer", "minimum": 1, "default": 1},
    }

    def _build_model(self, params, random_state):
        from sklearn.ensemble import ExtraTreesRegressor
        return ExtraTreesRegressor(
            n_estimators=int(params.get("n_estimators", 100)),
            max_depth=params.get("max_depth"),
            min_samples_leaf=int(params.get("min_samples_leaf", 1)),
            random_state=random_state,
        )
