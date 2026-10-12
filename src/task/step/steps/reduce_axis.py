# src/task/step/steps/reduce_axis.py
"""Reduce one axis of a form to summary statistics.

For each position along ``dim``, computes one or more summary
statistics over all other axes, and returns a new form in which
``dim`` is replaced by a ``"statistic"`` axis.

Layout
------
    input  dims: [..., dim, ...]     (any ndim >= 1)
    output dims: [..., "statistic"]  (dim removed)

The reduced dim is removed; every other dim keeps its original
order; the new ``"statistic"`` axis is appended last.

Supported statistics
--------------------
    sum        sum of values
    mean       mean of values
    std        standard deviation
    var        variance
    min        minimum
    max        maximum
    median     median
    nonzero    number of non-zero values
    count      number of non-missing values

Missing cells are identified via ``info["missing_code"]`` when set
and finite, otherwise via NaN. Every statistic except ``count`` and
``nonzero`` excludes missing cells; ``count`` and ``nonzero`` count
only non-missing cells.

Axis-parallel info for the reduced dim (as declared in
``axis_info[dim]``) is dropped from the output. Info entries for
surviving dims pass through unchanged. ``info["encoders"]`` is
trimmed to surviving dims.

Params:
    dim     : dimension to reduce (required)
    stats   : statistic name, or list of names (required)
    output  : context key for the result (default: step name)
"""

from __future__ import annotations

import warnings

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


_KNOWN_STATS = (
    "sum", "mean", "std", "var", "min", "max",
    "median", "nonzero", "count",
)


class ReduceAxisStep(Step):
    """Reduce one axis of a form to summary statistics."""

    name = "reduce_axis"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params.get("dim")
        stats = ctx.step_params.get("stats")
        out_name = ctx.step_params.get("output", self.name)

        if not dim:
            raise StepError("reduce_axis: 'dim' is required")
        if dim not in form.dims:
            raise StepError(
                f"reduce_axis: dim '{dim}' not present. "
                f"Available: {form.dims}"
            )
        if isinstance(stats, str):
            stats = [stats]
        if not isinstance(stats, list) or not stats:
            raise StepError(
                "reduce_axis: 'stats' must be a non-empty list of "
                "statistic names"
            )
        for s in stats:
            if s not in _KNOWN_STATS:
                raise StepError(
                    f"reduce_axis: unknown statistic '{s}'. "
                    f"Known: {list(_KNOWN_STATS)}"
                )
        if len(set(stats)) != len(stats):
            raise StepError(
                f"reduce_axis: duplicate statistic names: {stats}"
            )

        axis = form.dims.index(dim)
        data = form.data.astype(np.float64)

        missing_code = form.info.get("missing_code", np.nan)
        if isinstance(missing_code, float) and np.isnan(missing_code):
            missing = np.isnan(data)
        else:
            missing = data == missing_code

        moved = np.moveaxis(data, axis, -1)
        moved_missing = np.moveaxis(missing, axis, -1)
        original_shape = moved.shape
        n_reduced = original_shape[-1]
        flat = moved.reshape(-1, n_reduced)
        flat_missing = moved_missing.reshape(-1, n_reduced)
        valid = ~flat_missing

        computed = [
            _compute_stat(name, flat, valid) for name in stats
        ]
        stacked = np.stack(computed, axis=-1)
        out_shape = original_shape[:-1] + (len(stats),)
        out_data = stacked.reshape(out_shape).astype(np.float32)

        out_dims = [d for d in form.dims if d != dim] + ["statistic"]
        out_labels = {
            d: dict(form.labels[d]) for d in form.dims if d != dim
        }
        out_labels["statistic"] = {
            s: i for i, s in enumerate(stats)
        }

        reduced_parallel = set(form.axis_info.get(dim, []))
        out_info: dict = {}
        for k, v in form.info.items():
            if k in reduced_parallel:
                continue
            if k == "encoders" and isinstance(v, dict):
                trimmed = {
                    d: enc for d, enc in v.items() if d != dim
                }
                if trimmed:
                    out_info[k] = trimmed
                continue
            out_info[k] = v

        out_axis_info = {
            d: list(keys)
            for d, keys in form.axis_info.items()
            if d != dim
        }

        ctx[out_name] = Form(
            data=out_data,
            dims=out_dims,
            labels=out_labels,
            info=out_info,
            axis_info=out_axis_info,
        )

        n_outer = int(np.prod(original_shape[:-1])) if original_shape[:-1] else 1

        self._export_data = {
            "dim": dim,
            "stats": list(stats),
            "input_dims": list(form.dims),
            "input_shape": list(form.data.shape),
            "output_dims": out_dims,
            "output_shape": list(out_data.shape),
            "n_reduced": int(n_reduced),
            "n_outer": n_outer,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "stats": list(stats),
            "n_reduced": int(n_reduced),
            "n_outer": n_outer,
        }

        print(
            f"[reduce_axis] dim='{dim}' stats={list(stats)} "
            f"{form.data.shape} -> {out_data.shape}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _compute_stat(name: str, flat: np.ndarray, valid: np.ndarray):
    if name == "count":
        return valid.sum(axis=1).astype(np.float64)
    if name == "nonzero":
        nz = valid & (flat != 0)
        return nz.sum(axis=1).astype(np.float64)
    masked = np.where(valid, flat, np.nan)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        with np.errstate(invalid="ignore", divide="ignore"):
            if name == "sum":
                return np.nansum(masked, axis=1)
            if name == "mean":
                return np.nanmean(masked, axis=1)
            if name == "std":
                return np.nanstd(masked, axis=1)
            if name == "var":
                return np.nanvar(masked, axis=1)
            if name == "min":
                return np.nanmin(masked, axis=1)
            if name == "max":
                return np.nanmax(masked, axis=1)
            if name == "median":
                return np.nanmedian(masked, axis=1)
    raise StepError(f"reduce_axis: no implementation for '{name}'")