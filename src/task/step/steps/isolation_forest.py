from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix

class IsolationForestStep(Step):
    """Isolation Forest anomaly scores."""

    name = "isolation_forest"
    title = "Isolation Forest"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scikit-learn>=1.5"]
    dependency_imports = ["sklearn"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"

    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")]),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "n_estimators": {"type": "integer", "minimum": 1, "default": 100},
            "contamination": {"oneOf": [{"type": "string", "enum": ["auto"]}, {"type": "number", "exclusiveMinimum": 0, "maximum": 0.5}], "default": "auto"},
            "random_state": {"type": "integer", "default": 0},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from sklearn.ensemble import IsolationForest

        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        n_estimators = int(ctx.step_params.get("n_estimators", 100))
        contamination = ctx.step_params.get("contamination", "auto")
        random_state = int(ctx.step_params.get("random_state", 0))
        if isinstance(contamination, str):
            if contamination != "auto":
                raise StepError("isolation_forest: contamination must be 'auto' or a number in (0, 0.5]")
        else:
            contamination = float(contamination)
            if not 0.0 < contamination <= 0.5:
                raise StepError("isolation_forest: contamination must be in (0, 0.5]")
        X, sample_names, _ = matrix(form, sample_dim, feature_dim)
        model = IsolationForest(
            n_estimators=n_estimators,
            contamination=contamination,
            random_state=random_state,
        )
        model.fit(X)
        scores = model.score_samples(X)
        outlier = (model.predict(X) == -1).astype(np.float32)
        samples = list(sample_names)
        out_name = ctx.step_params.get("output", self.name)
        ctx[out_name] = Form(
            data=np.column_stack([scores.astype(np.float32), outlier]),
            dims=[sample_dim, "result"],
            labels={
                sample_dim: {name: i for i, name in enumerate(samples)},
                "result": {"score": 0, "outlier": 1},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "n_outliers": int(outlier.sum()),
            "contamination": contamination,
        }
        print(f"[isolation_forest] {len(samples)} samples, {int(outlier.sum())} outliers")

    def export(self, ctx: Context) -> dict:
        return self._export_data
