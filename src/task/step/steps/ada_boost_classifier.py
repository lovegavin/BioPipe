"""AdaBoost classifier."""
from __future__ import annotations

from ._ml_common import _ClassificationBase


class AdaBoostClassifierStep(_ClassificationBase):
    name = "ada_boost_classifier"
    title = "AdaBoost classifier"
    extra_properties = {
        "n_estimators": {"type": "integer", "minimum": 1, "default": 50},
        "learning_rate": {"type": "number", "exclusiveMinimum": 0, "default": 1.0},
    }

    def _build_model(self, params, random_state):
        from sklearn.ensemble import AdaBoostClassifier
        return AdaBoostClassifier(
            n_estimators=int(params.get("n_estimators", 50)),
            learning_rate=float(params.get("learning_rate", 1.0)),
            random_state=random_state,
        )
