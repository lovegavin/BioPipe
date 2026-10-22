"""Ordinary least squares linear regression."""
from __future__ import annotations
from ._ml_common import _RegressionBase


class LinearRegressionStep(_RegressionBase):
    name = "linear_regression"
    title = "Linear regression"
    extra_properties = {}

    def _build_model(self, params, random_state):
        from sklearn.linear_model import LinearRegression
        return LinearRegression()
