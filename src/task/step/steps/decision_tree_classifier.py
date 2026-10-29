"""Decision tree classifier."""
from __future__ import annotations

from ._ml_common import _ClassificationBase


class DecisionTreeClassifierStep(_ClassificationBase):
    name = "decision_tree_classifier"
    title = "Decision Tree classifier"
    extra_properties = {
        "criterion": {"type": "string", "enum": ["gini", "entropy", "log_loss"], "default": "gini"},
        "max_depth": {"type": ["integer", "null"], "minimum": 1, "default": None},
        "min_samples_split": {"type": "integer", "minimum": 2, "default": 2},
        "min_samples_leaf": {"type": "integer", "minimum": 1, "default": 1},
        "class_weight": {"type": ["string", "null"], "enum": ["balanced", None], "default": None},
    }

    def _build_model(self, params, random_state):
        from sklearn.tree import DecisionTreeClassifier
        return DecisionTreeClassifier(
            criterion=params.get("criterion", "gini"),
            max_depth=params.get("max_depth"),
            min_samples_split=int(params.get("min_samples_split", 2)),
            min_samples_leaf=int(params.get("min_samples_leaf", 1)),
            class_weight=params.get("class_weight"),
            random_state=random_state,
        )
