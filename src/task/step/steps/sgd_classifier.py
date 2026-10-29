"""Linear classifier trained with stochastic gradient descent."""
from __future__ import annotations

from ._ml_common import _ClassificationBase


class SgdClassifierStep(_ClassificationBase):
    name = "sgd_classifier"
    title = "SGD classifier"
    extra_properties = {
        "loss": {"type": "string", "enum": ["hinge", "log_loss", "modified_huber"], "default": "hinge"},
        "penalty": {"type": "string", "enum": ["l2", "l1", "elasticnet"], "default": "l2"},
        "alpha": {"type": "number", "exclusiveMinimum": 0, "default": 0.0001},
        "max_iter": {"type": "integer", "minimum": 1, "default": 1000},
    }

    def _build_model(self, params, random_state):
        from sklearn.linear_model import SGDClassifier
        return SGDClassifier(
            loss=params.get("loss", "hinge"),
            penalty=params.get("penalty", "l2"),
            alpha=float(params.get("alpha", 1e-4)),
            max_iter=int(params.get("max_iter", 1000)),
            random_state=random_state,
        )
