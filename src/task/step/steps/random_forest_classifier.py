"""Random Forest classifier."""
from __future__ import annotations
from ._ml_common import _ClassificationBase


class RandomForestClassifierStep(_ClassificationBase):
    name = "random_forest_classifier"
    title = "Random Forest classifier"
    extra_properties = {
        "n_estimators": {"type": "integer", "minimum": 1, "default": 100},
        "max_depth": {"type": ["integer", "null"], "minimum": 1,
                       "default": None},
        "class_weight": {
            "type": ["string", "null"], "enum": ["balanced", None],
            "default": None,
        },
    }

    def _build_model(self, params, random_state):
        from sklearn.ensemble import RandomForestClassifier
        return RandomForestClassifier(
            n_estimators=int(params.get("n_estimators", 100)),
            max_depth=params.get("max_depth"),
            class_weight=params.get("class_weight"),
            random_state=random_state,
        )
