"""Linear Discriminant Analysis classifier."""
from __future__ import annotations

from ._ml_common import _ClassificationBase


class LdaClassifierStep(_ClassificationBase):
    name = "lda_classifier"
    title = "Linear Discriminant Analysis classifier"
    extra_properties = {
        "solver": {"type": "string", "enum": ["svd", "lsqr", "eigen"], "default": "svd"},
        "tol": {"type": "number", "exclusiveMinimum": 0, "default": 0.0001},
    }

    def _build_model(self, params, random_state):
        from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
        return LinearDiscriminantAnalysis(
            solver=params.get("solver", "svd"),
            tol=float(params.get("tol", 1e-4)),
        )
