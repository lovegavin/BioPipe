"""Partial least-squares regression."""
from __future__ import annotations

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.cross_decomposition import PLSRegression

from ._ml_common import _RegressionBase


class _PlsRegressor(BaseEstimator, RegressorMixin):
    """PLSRegression adapter exposing a 1-D ``coef_`` for _MLBase.

    sklearn's PLSRegression stores ``coef_`` with shape
    ``(n_features, n_targets)`` for a single target.  The shared ML
    operator contract expects a one-dimensional coefficient vector, so
    this adapter flattens it after fitting while delegating prediction
    to the fitted estimator.
    """

    def __init__(self, n_components=2, max_iter=500, tol=1e-6):
        self.n_components = n_components
        self.max_iter = max_iter
        self.tol = tol

    def fit(self, X, y):
        self._model = PLSRegression(
            n_components=int(self.n_components),
            max_iter=int(self.max_iter),
            tol=float(self.tol),
            scale=False,
        )
        self._model.fit(X, y)
        self.coef_ = np.ravel(np.asarray(self._model.coef_, dtype=np.float64))
        return self

    def predict(self, X):
        return np.asarray(self._model.predict(X)).reshape(-1)


class PlsRegressionStep(_RegressionBase):
    name = "pls_regression"
    title = "PLS regression"
    extra_properties = {
        "n_components": {"type": "integer", "minimum": 1, "maximum": 100, "default": 2},
        "max_iter": {"type": "integer", "minimum": 1, "default": 500},
        "tol": {"type": "number", "exclusiveMinimum": 0, "default": 1e-6},
    }

    def _build_model(self, params, random_state):
        return _PlsRegressor(
            n_components=int(params.get("n_components", 2)),
            max_iter=int(params.get("max_iter", 500)),
            tol=float(params.get("tol", 1e-6)),
        )
