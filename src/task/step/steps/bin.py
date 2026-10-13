# src/task/step/steps/bin.py
"""Discretize a continuous axis into bins.

For each position along ``dim``, computes a bin index by cutting the
values along the other axes into equal-width or equal-frequency
intervals. The output has one row per position along ``dim`` and a
single integer bin id per row.

This is the standard way to turn a continuous quantity (age,
expression, allele frequency, distance) into a categorical one that
can be used by grouping operators such as ``aggregate`` or
``compare_groups``.

Value per position
------------------
Two ways to decide the value used to bin each position:

1. ``value_label`` : if given, the operator reads that column from
   the "other" axis (the one that is not ``dim``) and uses its
   values directly. This is the right choice when the input is a
   table whose second axis is a "statistic" axis with a single
   named column.

2. ``stat`` : if ``value_label`` is not given, the operator
   summarizes each position's values along the other axes with one
   of the following statistics:

       mean      mean over the other axes (default)
       median    median over the other axes
       min       minimum
       max       maximum
       first     first non-missing value

Missing cells are excluded from the summary.

Methods
-------
    quantile  equal-frequency bins: each bin holds roughly the same
              number of positions (default)
    uniform   equal-width bins: the value range is split into N
              equal intervals

Layout
------
    input   dims: [..., dim, ...]  (any ndim >= 1)
    output  dims: [dim, "bin"]

NaNs and out-of-range values
----------------------------
Positions whose value is NaN get bin id -1. Positions outside the
observed range (only possible with ``uniform``) get clamped to the
nearest bin.

Params:
    dim          : dimension to bin along (required)
    bins         : number of bins (default 10)
    method       : "quantile" | "uniform" (default "quantile")
    value_label  : optional column label on the other axis; if
                   given, that column's values are used directly
    stat         : summary name (default "mean"), ignored when
                   ``value_label`` is given
    output       : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._axis_contracts import SCHEMAS, CONTRACTS, estimate_axis
from ._microbiome import metadata


_METHODS = ("quantile", "uniform")
_STATS = ("mean", "median", "min", "max", "first")


class BinStep(Step):
    """Discretize a continuous axis into bins."""

    name = "bin"
    inputs_arity = 1
    outputs = []
    title = 'Bin'
    category = 'Analysis'
    builtin_package = 'biopipe-core'
    legacy_parameters = False
    parameters_schema = SCHEMAS['bin']
    input_contracts, output_contract = CONTRACTS['bin']
    output_parameter = 'output'

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return estimate_axis(cls.name, inputs, params, profiles)

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params.get("dim")
        bins = int(ctx.step_params.get("bins", 10))
        method = ctx.step_params.get("method", "quantile")
        value_label = ctx.step_params.get("value_label")
        stat = ctx.step_params.get("stat", "mean")
        out_name = ctx.step_params.get("output", self.name)

        if not dim:
            raise StepError("bin: 'dim' is required")
        if dim not in form.dims:
            raise StepError(
                f"bin: dim '{dim}' not present. "
                f"Available: {form.dims}"
            )
        if bins < 2:
            raise StepError(
                f"bin: bins must be >= 2, got {bins}"
            )
        if method not in _METHODS:
            raise StepError(
                f"bin: method must be one of {list(_METHODS)}, "
                f"got {method!r}"
            )
        if value_label is None and stat not in _STATS:
            raise StepError(
                f"bin: stat must be one of {list(_STATS)}, "
                f"got {stat!r}"
            )

        axis = form.dims.index(dim)
        n_positions = form.data.shape[axis]

        if value_label is not None:
            summaries, valid = _values_from_column(
                form, dim, value_label
            )
        else:
            moved = np.moveaxis(
                form.data, axis, 0
            ).astype(np.float64)
            flat = moved.reshape(n_positions, -1)

            missing_code = form.info.get("missing_code", np.nan)
            if isinstance(missing_code, float) and \
                    np.isnan(missing_code):
                missing = np.isnan(flat)
            else:
                missing = flat == missing_code
            masked = np.where(missing, np.nan, flat)

            summaries = _compute_summary(stat, masked)
            valid = np.isfinite(summaries)

        n_valid = int(valid.sum())
        if n_valid < 2:
            raise StepError(
                f"bin: fewer than 2 positions have a finite value"
            )

        values = summaries[valid]
        if method == "quantile":
            quantile_points = np.linspace(0, 1, bins + 1)
            edges = np.quantile(values, quantile_points)
            if np.unique(edges).size < 2:
                edges = np.linspace(
                    values.min(), values.max(), bins + 1
                )
        else:  # uniform
            lo, hi = float(values.min()), float(values.max())
            if lo == hi:
                hi = lo + 1e-9
            edges = np.linspace(lo, hi, bins + 1)

        bin_ids = np.full(n_positions, -1, dtype=int)
        raw = np.digitize(summaries, edges[1:-1], right=False)
        raw = np.clip(raw, 0, bins - 1)
        bin_ids[valid] = raw[valid]

        pos_to_label = {v: k for k, v in form.labels[dim].items()}
        ordered_labels = [
            pos_to_label.get(i, f"#{i}") for i in range(n_positions)
        ]

        out_data = bin_ids.astype(np.float32).reshape(-1, 1)
        info, axes = metadata(form, [dim], 'bins')
        ctx[out_name] = Form(
            data=out_data,
            dims=[dim, "bin"],
            labels={
                dim: dict(form.labels[dim]),
                "bin": {"bin": 0},
            },
            info=info, axis_info=axes,
        )

        bin_edges_list = [float(e) for e in edges]
        bin_of_label = {
            ordered_labels[i]: int(bin_ids[i])
            for i in range(n_positions)
        }
        bin_counts = {}
        for b in range(bins):
            members = [
                ordered_labels[i]
                for i in range(n_positions)
                if bin_ids[i] == b
            ]
            lo = float(edges[b])
            hi = float(edges[b + 1])
            bin_counts[str(b)] = {
                "n": len(members),
                "lo": lo,
                "hi": hi,
                "members": members,
            }

        self._export_data = {
            "dim": dim,
            "method": method,
            "stat": stat if value_label is None else None,
            "value_label": value_label,
            "bins": bins,
            "n_positions": int(n_positions),
            "n_valid": n_valid,
            "n_unbinned": int(n_positions - n_valid),
            "edges": bin_edges_list,
            "bin_of_label": bin_of_label,
            "bin_counts": bin_counts,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "method": method,
            "bins": bins,
            "n_valid": n_valid,
        }

        source = (
            f"value_label='{value_label}'"
            if value_label is not None else f"stat='{stat}'"
        )
        print(
            f"[bin] dim='{dim}' method='{method}' bins={bins} "
            f"{source} {n_positions} positions -> "
            f"{n_valid} binned"
            + (f" ({n_positions - n_valid} unbinned)"
               if n_positions - n_valid else "")
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _values_from_column(form: Form, dim: str, value_label: str):
    """Read one column from the 'other' axis of the form, returning
    a 1D array of length = form.data.shape[axis(dim)] plus a valid
    mask."""
    other_dims = [d for d in form.dims if d != dim]
    if not other_dims:
        raise StepError(
            f"bin: value_label requires at least two dims; "
            f"input has only '{dim}'"
        )
    other_dim = other_dims[0]
    if value_label not in form.labels.get(other_dim, {}):
        raise StepError(
            f"bin: value_label '{value_label}' not in dim "
            f"'{other_dim}'. Available: "
            f"{sorted(form.labels.get(other_dim, {}))}"
        )
    col_pos = form.labels[other_dim][value_label]
    col_axis = form.dims.index(other_dim)
    values = np.take(form.data, col_pos, axis=col_axis).astype(
        np.float64
    )

    missing_code = form.info.get("missing_code", np.nan)
    if isinstance(missing_code, float) and np.isnan(missing_code):
        missing = np.isnan(values)
    else:
        missing = values == missing_code
    valid = ~missing
    return values, valid


def _compute_summary(stat: str, masked: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        if stat == "mean":
            return np.nanmean(masked, axis=1)
        if stat == "median":
            return np.nanmedian(masked, axis=1)
        if stat == "min":
            return np.nanmin(masked, axis=1)
        if stat == "max":
            return np.nanmax(masked, axis=1)
        if stat == "first":
            n_positions, _ = masked.shape
            out = np.full(n_positions, np.nan)
            for i in range(n_positions):
                row = masked[i]
                finite = row[np.isfinite(row)]
                if finite.size:
                    out[i] = finite[0]
            return out
    raise StepError(f"bin: no implementation for '{stat}'")