"""ROC curve for binary labels and a numeric score."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import roc_curve

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._metric_common import binary_truth, label_series, score_series


class RocCurveStep(Step):
    """ROC curve points (FPR, TPR, threshold) for a binary target."""

    name = "roc_curve"
    title = "ROC curve"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scikit-learn>=1.5"]
    dependency_imports = ["sklearn"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("label_dim", "label")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("score_dim", "score")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "label_dim": {"type": "string", "default": "label"},
            "score_dim": {"type": "string", "default": "score"},
            "target_label": {"type": "string"},
            "score_label": {"type": "string"},
            "positive_label": {"type": "string"},
            "output": {"type": "string"},
        },
        "required": ["target_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        label_form, score_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        label_dim = ctx.step_params.get("label_dim", "label")
        score_dim = ctx.step_params.get("score_dim", "score")
        label_samples, labels = label_series(label_form, sample_dim, label_dim, ctx.step_params["target_label"], "roc_curve")
        score_samples, scores = score_series(
            score_form, sample_dim, score_dim,
            ctx.step_params.get("score_label") or next(iter(score_form.labels[score_dim])),
        )
        pos = {name: i for i, name in enumerate(score_samples)}
        keep = [i for i, name in enumerate(label_samples) if name in pos]
        if len(keep) < 4:
            raise StepError("roc_curve: fewer than four shared samples")
        y_labels = [labels[i] for i in keep]
        y_scores = np.asarray([scores[pos[label_samples[i]]] for i in keep], dtype=np.float64)
        classes, positive, y_true = binary_truth(label_samples, y_labels, ctx.step_params.get("positive_label"))
        fpr, tpr, thresholds = roc_curve(y_true, y_scores, drop_intermediate=False)
        data = np.column_stack([fpr, tpr, thresholds]).astype(np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=data,
            dims=["threshold", "statistic"],
            labels={
                "threshold": {f"t{i}": i for i in range(data.shape[0])},
                "statistic": {"fpr": 0, "tpr": 1, "threshold": 2},
            },
            info={"missing_code": np.nan, "positive_label": positive, "classes": classes},
        )
        self._export_data = {"n_samples": len(y_true), "n_points": int(data.shape[0]), "positive_label": positive}
        print(f"[roc_curve] n={len(y_true)}, points={data.shape[0]}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
