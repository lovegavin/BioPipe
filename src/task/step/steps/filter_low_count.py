# src/task/step/steps/filter_low_count.py
"""Filter low-count positions along one dimension.

Keeps positions whose count reaches ``min_count`` in at least
``min_samples`` samples. The standard first QC step for any
count-based matrix (RNA-seq, single-cell, metagenomics, proteomics).

Layout
------
Input is any Form. The filter runs along ``dim``; every other axis
is treated as a sample axis and flattened.

    pass[i, j] = valid[i, j] and data[i, j] >= min_count
    keep[i]    = sum_j(pass[i, j]) >= min_samples

Missing values never count as a passing sample.

Params:
    dim         : dimension to filter along
    min_count   : per-sample count threshold (default 1)
    min_samples : minimum number of samples that must pass
                  (default 1)
    output      : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class FilterLowCountStep(Step):
    """Drop positions that do not reach a minimum count."""

    name = "filter_low_count"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params["dim"]
        min_count = float(ctx.step_params.get("min_count", 1))
        min_samples = int(ctx.step_params.get("min_samples", 1))
        out_name = ctx.step_params.get("output", self.name)

        if dim not in form.dims:
            raise StepError(
                f"filter_low_count: dim '{dim}' is not present. "
                f"Available: {form.dims}"
            )
        if min_count < 0:
            raise StepError(
                f"filter_low_count: min_count must be >= 0, "
                f"got {min_count}"
            )
        if min_samples < 1:
            raise StepError(
                f"filter_low_count: min_samples must be >= 1, "
                f"got {min_samples}"
            )

        axis = form.dims.index(dim)
        moved = np.moveaxis(form.data, axis, 0)
        n_positions = moved.shape[0]
        flat = moved.reshape(n_positions, -1)

        missing_code = form.info.get("missing_code", np.nan)
        if isinstance(missing_code, float) and np.isnan(missing_code):
            valid = ~np.isnan(flat)
        else:
            valid = flat != missing_code

        passing = valid & (flat >= min_count)
        n_pass = passing.sum(axis=1)
        keep = n_pass >= min_samples

        n_before = int(n_positions)
        n_after = int(keep.sum())
        if n_after == 0:
            raise StepError(
                f"filter_low_count: threshold removed every position "
                f"along '{dim}'."
            )

        kept = np.where(keep)[0]
        new_form = form.subset_axis(dim, kept)
        ctx[out_name] = new_form

        pos_to_label = {v: k for k, v in form.labels[dim].items()}
        kept_labels = [pos_to_label[int(i)] for i in kept]
        kept_set = set(kept.tolist())
        dropped_labels = [
            pos_to_label[i] for i in range(n_before)
            if i not in kept_set
        ]
        n_pass_by_label = {
            pos_to_label[i]: int(n_pass[i])
            for i in range(n_before)
        }

        self._export_data = {
            "dim": dim,
            "min_count": min_count,
            "min_samples": min_samples,
            "n_before": n_before,
            "n_after": n_after,
            "n_removed": n_before - n_after,
            "kept_labels": kept_labels,
            "dropped_labels": dropped_labels,
            "n_pass_by_label": n_pass_by_label,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "min_count": min_count,
            "min_samples": min_samples,
            "n_before": n_before,
            "n_after": n_after,
            "n_removed": n_before - n_after,
        }

        print(
            f"[filter_low_count] dim='{dim}' {n_before} -> {n_after} "
            f"(min_count={min_count}, min_samples={min_samples})"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data