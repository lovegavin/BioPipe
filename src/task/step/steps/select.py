# src/task/step/steps/select.py
"""Select step: keep a subset of labels along one dimension."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class SelectStep(Step):
    """Keep only the listed labels along one dimension.

    Params:
        dim    : dimension to select along
        labels : list of label names to keep, in output order
        output : context key for the result
    """

    name = "select"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params["dim"]
        labels = ctx.step_params["labels"]
        out_name = ctx.step_params.get("output", self.name)

        if dim not in form.dims:
            raise StepError(f"select: dim '{dim}' not in {form.dims}")
        if not isinstance(labels, list) or not labels:
            raise StepError("select: 'labels' must be a non-empty list")

        dim_labels = form.labels.get(dim, {})
        if not dim_labels:
            raise StepError(
                f"select: dim '{dim}' has no labels to select from"
            )

        missing = [l for l in labels if l not in dim_labels]
        if missing:
            raise StepError(
                f"select: labels not found on dim '{dim}': {missing}. "
                f"Available: {sorted(dim_labels)}"
            )

        axis = form.dims.index(dim)
        positions = [dim_labels[l] for l in labels]

        index = [slice(None)] * form.data.ndim
        index[axis] = positions
        new_data = form.data[tuple(index)].copy()

        new_labels = {k: dict(v) for k, v in form.labels.items()}
        new_labels[dim] = {l: i for i, l in enumerate(labels)}

        ctx[out_name] = Form(
            data=new_data.astype(np.float32),
            dims=list(form.dims),
            labels=new_labels,
            info=dict(form.info),
        )

        self._export_data = {
            "dim": dim,
            "n_before": int(form.data.shape[axis]),
            "n_after": len(labels),
            "selected_labels": list(labels),
        }

        print(
            f"[select] dim '{dim}': {len(labels)} labels kept "
            f"-> {out_name}, shape={new_data.shape}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data