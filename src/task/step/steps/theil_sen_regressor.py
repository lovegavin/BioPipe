"""Robust Theil-Sen regression."""
from __future__ import annotations

from ._ml_common import _RegressionBase


class TheilSenRegressorStep(_RegressionBase):
    name = "theil_sen_regressor"
    title = "Theil-Sen regressor"
    extra_properties = {
        "max_subpopulation": {"type": "integer", "minimum": 10, "default": 10000},
        "max_iter": {"type": "integer", "minimum": 1, "default": 300},
    }

    def _build_model(self, params, random_state):
        from sklearn.linear_model import TheilSenRegressor
        return TheilSenRegressor(
            max_subpopulation=int(params.get("max_subpopulation", 10000)),
            max_iter=int(params.get("max_iter", 300)),
            random_state=random_state,
        )
