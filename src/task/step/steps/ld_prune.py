# src/task/step/steps/ld_prune.py
"""LD pruning."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class LdPruneStep(Step):
    """Prune positions along one dimension by LD.

    Params:
        dim    : dimension to prune along
        window : window size in positions
        r2     : r^2 threshold
        output : context key for the result
    """

    name = "ld_prune"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params["dim"]
        window = int(ctx.step_params.get("window", 50))
        r2_threshold = float(ctx.step_params.get("r2", 0.2))
        out_name = ctx.step_params.get("output", self.name)

        if "missing_code" not in form.info:
            raise StepError(
                f"Form has no info['missing_code']. "
                f"Available: {sorted(form.info)}"
            )
        if dim not in form.dims:
            raise StepError(
                f"Dim '{dim}' is not present. Available: {form.dims}"
            )

        axis = form.dims.index(dim)
        moved = np.moveaxis(form.data, axis, 0)
        n_positions = moved.shape[0]
        flat = moved.reshape(n_positions, -1).astype(np.float64)

        missing_code = form.info["missing_code"]
        if isinstance(missing_code, float) and np.isnan(missing_code):
            missing = np.isnan(flat)
        else:
            missing = flat == missing_code

        keep = np.ones(n_positions, dtype=bool)
        for i in range(n_positions):
            if not keep[i]:
                continue
            upper = min(i + window + 1, n_positions)
            for j in range(i + 1, upper):
                if not keep[j]:
                    continue
                if _r2(flat[i], flat[j], missing[i], missing[j]) > r2_threshold:
                    keep[j] = False

        kept = np.where(keep)[0]
        n_before = n_positions
        n_after = len(kept)

        if n_after == 0:
            raise StepError("ld_prune: every position was pruned")

        new_form = form.subset_axis(dim, kept)
        ctx[out_name] = new_form

        pos_to_label = {v: k for k, v in form.labels[dim].items()}
        all_labels = [pos_to_label[i] for i in range(n_before)]
        kept_labels = [pos_to_label[int(i)] for i in kept]
        kept_set = set(kept.tolist())
        dropped_labels = [
            pos_to_label[i] for i in range(n_before)
            if i not in kept_set
        ]

        self._export_data = {
            "dim": dim,
            "window": window,
            "r2_threshold": r2_threshold,
            "n_before": int(n_before),
            "n_after": n_after,
            "n_removed": int(n_before - n_after),
            "all_labels": all_labels,
            "kept_labels": kept_labels,
            "dropped_labels": dropped_labels,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "window": window,
            "r2_threshold": r2_threshold,
            "n_before": int(n_before),
            "n_after": n_after,
            "n_removed": int(n_before - n_after),
        }

        print(
            f"[ld_prune] dim='{dim}' {n_before} -> {n_after} "
            f"(window={window}, r2>{r2_threshold})"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _r2(x, y, x_missing, y_missing):
    valid = ~(x_missing | y_missing)
    n = int(valid.sum())
    if n < 3:
        return 0.0
    xv = x[valid]
    yv = y[valid]
    if xv.std() < 1e-12 or yv.std() < 1e-12:
        return 0.0
    r = float(np.corrcoef(xv, yv)[0, 1])
    if not np.isfinite(r):
        return 0.0
    return r * r