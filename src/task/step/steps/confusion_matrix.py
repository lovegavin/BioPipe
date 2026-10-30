"""Confusion matrix for two binary label columns."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._metric_common import label_series


class ConfusionMatrixStep(Step):
    """Binary confusion matrix with actual rows and predicted columns."""

    name = "confusion_matrix"
    title = "Confusion matrix"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.26"]
    dependency_imports = ["numpy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sample_dim", "sample"), param("label_dim", "label")])]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "label_dim": {"type": "string", "default": "label"},
            "true_label": {"type": "string"},
            "pred_label": {"type": "string"},
            "output": {"type": "string"},
        },
        "required": ["true_label", "pred_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        label_dim = ctx.step_params.get("label_dim", "label")
        samples, true = label_series(form, sample_dim, label_dim, ctx.step_params["true_label"], "confusion_matrix")
        _, pred = label_series(form, sample_dim, label_dim, ctx.step_params["pred_label"], "confusion_matrix")
        classes = sorted(set(true) | set(pred))
        if len(classes) != 2:
            raise StepError(f"confusion_matrix: need exactly two classes, got {classes}")
        index = {name: i for i, name in enumerate(classes)}
        matrix = np.zeros((2, 2), dtype=np.float32)
        for a, b in zip(true, pred):
            matrix[index[a], index[b]] += 1
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=matrix,
            dims=["actual", "predicted"],
            labels={
                "actual": {name: i for i, name in enumerate(classes)},
                "predicted": {name: i for i, name in enumerate(classes)},
            },
            info={"missing_code": np.nan, "classes": classes},
        )
        self._export_data = {"classes": classes, "n_samples": len(samples), "matrix": matrix.tolist()}
        print(f"[confusion_matrix] {len(samples)} samples, classes={classes}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
