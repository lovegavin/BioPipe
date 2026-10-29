"""Complement Naive Bayes classifier; expects non-negative features."""
from __future__ import annotations

from ._ml_common import _ClassificationBase
from ._nb_common import ComplementNBWithCoef


class ComplementNBClassifierStep(_ClassificationBase):
    name = "complement_nb_classifier"
    title = "Complement Naive Bayes classifier"
    extra_properties = {
        "scale": {"type": "boolean", "default": False},
        "alpha": {"type": "number", "exclusiveMinimum": 0, "default": 1.0},
        "fit_prior": {"type": "boolean", "default": True},
        "norm": {"type": "boolean", "default": False},
    }

    def _build_model(self, params, random_state):
        
        return ComplementNBWithCoef(
            alpha=float(params.get("alpha", 1.0)),
            fit_prior=bool(params.get("fit_prior", True)),
            norm=bool(params.get("norm", False)),
        )
