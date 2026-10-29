"""Multinomial Naive Bayes classifier; expects non-negative features."""
from __future__ import annotations

from ._ml_common import _ClassificationBase
from ._nb_common import MultinomialNBWithCoef


class MultinomialNBClassifierStep(_ClassificationBase):
    name = "multinomial_nb_classifier"
    title = "Multinomial Naive Bayes classifier"
    extra_properties = {
        "scale": {"type": "boolean", "default": False},
        "alpha": {"type": "number", "exclusiveMinimum": 0, "default": 1.0},
        "fit_prior": {"type": "boolean", "default": True},
    }

    def _build_model(self, params, random_state):
        
        return MultinomialNBWithCoef(
            alpha=float(params.get("alpha", 1.0)),
            fit_prior=bool(params.get("fit_prior", True)),
        )
