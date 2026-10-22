"""Linear SVM classifier."""
from __future__ import annotations
from ._ml_common import _ClassificationBase


class SvmClassifierStep(_ClassificationBase):
    name = "svm_classifier"
    title = "Linear SVM classifier"
    extra_properties = {
        "C": {"type": "number", "exclusiveMinimum": 0, "default": 1.0},
        "class_weight": {
            "type": ["string", "null"], "enum": ["balanced", None],
            "default": None,
        },
    }

    def _build_model(self, params, random_state):
        from sklearn.svm import SVC
        return SVC(
            C=float(params.get("C", 1.0)),
            kernel="linear", probability=True,
            class_weight=params.get("class_weight"),
            random_state=random_state,
        )
