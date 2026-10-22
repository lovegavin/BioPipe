"""Gradient Boosting classifier."""
from __future__ import annotations
from ._ml_common import _ClassificationBase


class GradientBoostingClassifierStep(_ClassificationBase):
    name = "gradient_boosting_classifier"
    title = "Gradient Boosting classifier"
    extra_properties = {
        "n_estimators": {"type": "integer", "minimum": 1, "default": 100},
        "learning_rate": {"type": "number", "exclusiveMinimum": 0,
                            "default": 0.1},
        "max_depth": {"type": "integer", "minimum": 1, "default": 3},
    }

    def _build_model(self, params, random_state):
        from sklearn.ensemble import GradientBoostingClassifier
        return GradientBoostingClassifier(
            n_estimators=int(params.get("n_estimators", 100)),
            learning_rate=float(params.get("learning_rate", 0.1)),
            max_depth=int(params.get("max_depth", 3)),
            random_state=random_state,
        )
