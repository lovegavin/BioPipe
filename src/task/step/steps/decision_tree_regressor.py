"""Decision tree regressor."""
from __future__ import annotations

from ._ml_common import _RegressionBase


class DecisionTreeRegressorStep(_RegressionBase):
    name = "decision_tree_regressor"
    title = "Decision Tree regressor"
    extra_properties = {
        "criterion": {"type": "string", "enum": ["squared_error", "absolute_error", "friedman_mse", "poisson"], "default": "squared_error"},
        "max_depth": {"type": ["integer", "null"], "minimum": 1, "default": None},
        "min_samples_split": {"type": "integer", "minimum": 2, "default": 2},
        "min_samples_leaf": {"type": "integer", "minimum": 1, "default": 1},
    }

    def _build_model(self, params, random_state):
        from sklearn.tree import DecisionTreeRegressor
        return DecisionTreeRegressor(
            criterion=params.get("criterion", "squared_error"),
            max_depth=params.get("max_depth"),
            min_samples_split=int(params.get("min_samples_split", 2)),
            min_samples_leaf=int(params.get("min_samples_leaf", 1)),
            random_state=random_state,
        )
