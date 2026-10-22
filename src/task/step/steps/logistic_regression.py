"""Logistic regression classifier (L1 or L2 penalty)."""
from __future__ import annotations
from ._ml_common import _ClassificationBase


class LogisticRegressionStep(_ClassificationBase):
    name = "logistic_regression"
    title = "Logistic regression"
    extra_properties = {
        "C": {"type": "number", "exclusiveMinimum": 0, "default": 1.0},
        "penalty": {"type": "string", "enum": ["l2", "l1"], "default": "l2"},
        "class_weight": {
            "type": ["string", "null"], "enum": ["balanced", None],
            "default": None,
        },
    }

    def _build_model(self, params, random_state):
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression(
            C=float(params.get("C", 1.0)),
            penalty=params.get("penalty", "l2"),
            max_iter=2000,
            class_weight=params.get("class_weight"),
            random_state=random_state,
        )
