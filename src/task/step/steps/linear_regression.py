"""Ordinary least-squares linear regression."""
from __future__ import annotations

from ._ml_common import _RegressionBase


class LinearRegressionStep(_RegressionBase):
    name = "linear_regression"
    title = "Linear regression"
    extra_properties = {
        "fit_intercept": {"type": "boolean", "default": True},
        "positive": {"type": "boolean", "default": False},
    }

    def _build_model(self, params, random_state):
        from sklearn.linear_model import LinearRegression
        return LinearRegression(
            fit_intercept=bool(params.get("fit_intercept", True)),
            positive=bool(params.get("positive", False)),
        )
