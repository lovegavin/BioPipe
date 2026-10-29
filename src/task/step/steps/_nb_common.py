"""Naive Bayes adapters exposing a coef_ attribute for the ML base."""
from __future__ import annotations

import numpy as np
from sklearn.naive_bayes import ComplementNB, MultinomialNB


class _CoefMixin:
    def fit(self, X, y, **kwargs):
        super().fit(X, y, **kwargs)
        self.coef_ = np.asarray(self.feature_log_prob_, dtype=np.float64)
        return self


class ComplementNBWithCoef(_CoefMixin, ComplementNB):
    """ComplementNB whose log-probabilities are exposed as coef_."""


class MultinomialNBWithCoef(_CoefMixin, MultinomialNB):
    """MultinomialNB whose log-probabilities are exposed as coef_."""
