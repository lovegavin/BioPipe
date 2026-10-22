"""Linear epsilon-SVR regressor."""
from __future__ import annotations
from ._ml_common import _RegressionBase


class SvmRegressorStep(_RegressionBase):
    name = "svm_regressor"
    title = "Linear SVM regressor"
    extra_properties = {
        "C": {"type": "number", "exclusiveMinimum": 0, "default": 1.0},
        "epsilon": {"type": "number", "exclusiveMinimum": 0,
                     "default": 0.1},
    }

    def _build_model(self, params, random_state):
        from sklearn.svm import SVR
        return SVR(
            C=float(params.get("C", 1.0)),
            epsilon=float(params.get("epsilon", 0.1)),
            kernel="linear",
        )
