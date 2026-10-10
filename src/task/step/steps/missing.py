# src/task/step/steps/missing.py
"""Missingness filter along one dimension."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class MissingStep(Step):
    """Filter positions along one dimension by missing rate.

    Params:
        dim       : dimension to filter on
        threshold : maximum allowed missing rate
        output    : context key for the result (default: step name)
    """

    name = "missing"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params["dim"]
        threshold = float(ctx.step_params.get("threshold", 0.10))
        out_name = ctx.step_params.get("output", self.name)

        if "missing_code" not in form.info:
            raise StepError(
                f"Form has no info['missing_code']. "
                f"Available: {sorted(form.info)}"
            )
        if dim not in form.dims:
            raise StepError(
                f"Dim '{dim}' is not present on the form. "
                f"Available: {form.dims}"
            )

        axis = form.dims.index(dim)
        other_axes = tuple(i for i in range(form.data.ndim) if i != axis)

        missing_code = form.info["missing_code"]
        if isinstance(missing_code, float) and np.isnan(missing_code):
            mask = np.isnan(form.data)
        else:
            mask = form.data == missing_code

        per_pos = mask.mean(axis=other_axes)
        keep = per_pos <= threshold
        n_before = form.data.shape[axis]
        n_after = int(keep.sum())

        if n_after == 0:
            raise StepError(
                f"missing: threshold removed every position along "
                f"'{dim}'. threshold={threshold}"
            )

        kept = np.where(keep)[0]
        new_form = form.subset_axis(dim, kept)
        ctx[out_name] = new_form

        pos_to_label = {v: k for k, v in form.labels[dim].items()}
        missing_rate_by_label = {
            pos_to_label[i]: float(per_pos[i])
            for i in range(n_before)
        }

        self._export_data = {
            "dim": dim,
            "threshold": threshold,
            "n_before": int(n_before),
            "n_after": n_after,
            "n_removed": int(n_before - n_after),
            "missing_rate_by_label": missing_rate_by_label,
            "kept_labels": [
                pos_to_label[int(i)] for i in kept
            ],
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "threshold": threshold,
            "n_before": int(n_before),
            "n_after": n_after,
            "n_removed": int(n_before - n_after),
        }

        print(
            f"[missing] dim='{dim}' {n_before} -> {n_after} "
            f"(threshold={threshold})"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data