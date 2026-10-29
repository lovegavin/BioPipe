"""Bayesian ridge regression with automatic regularisation."""
from __future__ import annotations

from ._ml_common import _RegressionBase


class BayesianRidgeRegressorStep(_RegressionBase):
    name = "bayesian_ridge_regressor"
    title = "Bayesian ridge regressor"
    extra_properties = {
        "alpha_1": {"type": "number", "exclusiveMinimum": 0, "default": 0.000001},
        "alpha_2": {"type": "number", "exclusiveMinimum": 0, "default": 0.000001},
        "lambda_1": {"type": "number", "exclusiveMinimum": 0, "default": 0.000001},
        "lambda_2": {"type": "number", "exclusiveMinimum": 0, "default": 0.000001},
    }

    def _build_model(self, params, random_state):
        from sklearn.linear_model import BayesianRidge
        return BayesianRidge(
            alpha_1=float(params.get("alpha_1", 1e-6)),
            alpha_2=float(params.get("alpha_2", 1e-6)),
            lambda_1=float(params.get("lambda_1", 1e-6)),
            lambda_2=float(params.get("lambda_2", 1e-6)),
        )
