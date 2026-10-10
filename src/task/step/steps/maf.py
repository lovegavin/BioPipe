# src/task/step/steps/maf.py
"""Minor allele frequency filter."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class MafStep(Step):
    """Filter positions along one dimension by MAF.

    Params:
        dim       : dimension to compute MAF along
        threshold : minimum allowed MAF
        output    : context key for the result
    """

    name = "maf"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params["dim"]
        threshold = float(ctx.step_params.get("threshold", 0.01))
        out_name = ctx.step_params.get("output", self.name)

        for field in ("missing_code", "ploidy"):
            if field not in form.info:
                raise StepError(
                    f"Form has no info['{field}']. "
                    f"Available: {sorted(form.info)}"
                )
        if dim not in form.dims:
            raise StepError(
                f"Dim '{dim}' is not present. Available: {form.dims}"
            )

        axis = form.dims.index(dim)
        other_axes = tuple(i for i in range(form.data.ndim) if i != axis)

        missing_code = form.info["missing_code"]
        ploidy = int(form.info["ploidy"])

        if isinstance(missing_code, float) and np.isnan(missing_code):
            missing = np.isnan(form.data)
        else:
            missing = form.data == missing_code

        valid = ~missing
        n_valid = valid.sum(axis=other_axes)
        allele_sum = np.where(valid, form.data, 0.0).sum(axis=other_axes)

        with np.errstate(invalid="ignore", divide="ignore"):
            alt_freq = allele_sum / (ploidy * n_valid)

        alt_freq = np.where(n_valid > 0, alt_freq, np.nan)
        maf = np.minimum(alt_freq, 1.0 - alt_freq)

        keep = (~np.isnan(maf)) & (maf >= threshold)
        n_before = form.data.shape[axis]
        n_after = int(keep.sum())

        if n_after == 0:
            raise StepError(
                f"maf: threshold removed every position along '{dim}'"
            )

        kept = np.where(keep)[0]
        new_form = form.subset_axis(dim, kept)
        ctx[out_name] = new_form

        pos_to_label = {v: k for k, v in form.labels[dim].items()}
        maf_by_label = {
            pos_to_label[i]: (
                float(maf[i]) if np.isfinite(maf[i]) else None
            )
            for i in range(n_before)
        }
        maf_kept_by_label = {
            pos_to_label[int(i)]: float(maf[i]) for i in kept
        }

        self._export_data = {
            "dim": dim,
            "threshold": threshold,
            "ploidy": ploidy,
            "n_before": int(n_before),
            "n_after": n_after,
            "n_removed": int(n_before - n_after),
            "maf_by_label": maf_by_label,
            "maf_kept_by_label": maf_kept_by_label,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "threshold": threshold,
            "n_before": int(n_before),
            "n_after": n_after,
            "n_removed": int(n_before - n_after),
        }

        print(
            f"[maf] dim='{dim}' {n_before} -> {n_after} "
            f"(threshold={threshold})"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data