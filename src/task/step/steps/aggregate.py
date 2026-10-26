# src/task/step/steps/aggregate.py
"""Aggregate positions along one axis by group.

Two inputs share an axis (the "row" axis). The first input carries
values; the second carries a group label for each position. For
each group, the operator collapses all positions in that group
into a single row by applying a reduction (sum, mean, median, ...).

This is the natural companion of ``join``: where ``join`` attaches
metadata columns to a form, ``aggregate`` reduces a form by a
metadata column. Typical uses:

    - collapse species to genus before plotting composition
    - collapse cells to clusters before profiling
    - collapse genes to pathways before scoring
    - collapse any [row, other] matrix by a [row, group] table

Layout
------
    data    dims: [row_dim, other_dim]   (any two axes)
    groups  dims: [row_dim, group_dim]   (same row_dim first)
    output  dims: [group_dim, other_dim]

Both inputs must be 2D with ``dim`` as their first axis. To use a
form whose shared axis is second, transpose it first.

Reductions
----------
    sum       sum of values in the group
    mean      mean of values in the group
    median    median of values in the group
    min       minimum
    max       maximum
    count     number of non-missing values in the group

Missing cells are excluded before the reduction, except for
``count`` where they are dropped from the count.

Group labels
------------
The group column can be a numeric column (each value is used as a
group key) or an encoded string column (the encoder's inverse map
is used to recover group names). The output group labels are the
recovered names, sorted by first appearance in the input order.

Params:
    dim        : shared dim name (required)
    group_col  : column label on the groups form (required)
    method     : reduction name (default "sum")
    output     : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._microbiome import CONTRACTS, SCHEMAS, estimate, metadata


_METHODS = ("sum", "mean", "median", "min", "max", "count")


class AggregateStep(Step):
    """Aggregate positions along one axis by group."""
    description = 'Aggregate positions along one axis by group.'

    name = "aggregate"
    inputs_arity = 2
    outputs = []
    title = 'Aggregate'
    category = '数据整理'
    builtin_package = "biopipe-microbiome"
    parameters_schema = SCHEMAS['aggregate']
    input_contracts, output_contract = CONTRACTS['aggregate']
    output_parameter = "output"

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return estimate(cls.name, inputs, params, profiles)

    def run(self, ctx: Context, inputs) -> None:
        data_form, groups_form = inputs
        dim = ctx.step_params.get("dim")
        group_col = ctx.step_params.get("group_col")
        method = ctx.step_params.get("method", "sum")
        out_name = ctx.step_params.get("output", self.name)

        if not dim:
            raise StepError("aggregate: 'dim' is required")
        if not group_col:
            raise StepError("aggregate: 'group_col' is required")
        if method not in _METHODS:
            raise StepError(
                f"aggregate: method must be one of {list(_METHODS)}, "
                f"got {method!r}"
            )
        if data_form.data.ndim != 2:
            raise StepError(
                f"aggregate: data form must be 2D, "
                f"got ndim={data_form.data.ndim}"
            )
        if groups_form.data.ndim != 2:
            raise StepError(
                f"aggregate: groups form must be 2D, "
                f"got ndim={groups_form.data.ndim}"
            )
        if data_form.dims[0] != dim:
            raise StepError(
                f"aggregate: data's first dim must be '{dim}', "
                f"got '{data_form.dims[0]}'. Use transpose if needed."
            )
        if groups_form.dims[0] != dim:
            raise StepError(
                f"aggregate: groups' first dim must be '{dim}', "
                f"got '{groups_form.dims[0]}'. Use transpose if needed."
            )

        other_dim = data_form.dims[1]
        group_dim = groups_form.dims[1]

        if group_col not in groups_form.labels[group_dim]:
            raise StepError(
                f"aggregate: group_col '{group_col}' not in dim "
                f"'{group_dim}'. Available: "
                f"{sorted(groups_form.labels[group_dim])}"
            )

        data_row_labels = data_form.labels[dim]
        groups_row_labels = groups_form.labels[dim]
        common = [
            l for l in data_row_labels if l in groups_row_labels
        ]
        if not common:
            raise StepError(
                f"aggregate: no common row labels on '{dim}'"
            )

        data_idx = [data_row_labels[l] for l in common]
        group_idx = [groups_row_labels[l] for l in common]

        # Extract the group code for each shared row.
        col_pos = groups_form.labels[group_dim][group_col]
        group_codes_raw = groups_form.data[group_idx, col_pos]
        group_codes_raw = np.where(group_codes_raw == groups_form.info.get("missing_code", np.nan), np.nan, group_codes_raw)

        # Recover the human-readable group label.
        encoders = groups_form.info.get("encoders", {})
        encoder = None
        if group_dim in encoders and group_col in encoders[group_dim]:
            encoder = encoders[group_dim][group_col]

        group_names = [
            _decode(c, encoder) for c in group_codes_raw
        ]
        valid = np.array([g is not None for g in group_names])
        if not valid.any():
            raise StepError(
                "aggregate: no rows with a valid group value"
            )

        # Group order: first appearance in the input order.
        seen: dict[str, int] = {}
        ordered_groups: list[str] = []
        for g, v in zip(group_names, valid):
            if not v:
                continue
            if g not in seen:
                seen[g] = len(ordered_groups)
                ordered_groups.append(g)

        n_groups = len(ordered_groups)
        n_other = data_form.data.shape[1]
        out_data = np.full((n_groups, n_other), np.nan, dtype=np.float64)

        missing_code = data_form.info.get("missing_code", np.nan)
        if isinstance(missing_code, float) and np.isnan(missing_code):
            missing = np.isnan(data_form.data)
        else:
            missing = data_form.data == missing_code

        # Aggregate row by row.
        for gi, g in enumerate(ordered_groups):
            rows = [
                di for di, gn, v in
                zip(data_idx, group_names, valid)
                if v and gn == g
            ]
            if not rows:
                continue
            block = data_form.data[rows, :].astype(np.float64)
            block_missing = missing[rows, :]
            masked = np.where(block_missing, np.nan, block)

            with np.errstate(invalid="ignore", divide="ignore"):
                if method == "sum":
                    out_data[gi] = np.nansum(masked, axis=0)
                elif method == "mean":
                    out_data[gi] = np.nanmean(masked, axis=0)
                elif method == "median":
                    out_data[gi] = np.nanmedian(masked, axis=0)
                elif method == "min":
                    out_data[gi] = np.nanmin(masked, axis=0)
                elif method == "max":
                    out_data[gi] = np.nanmax(masked, axis=0)
                elif method == "count":
                    out_data[gi] = (~block_missing).sum(axis=0)

        out_labels = {
            group_dim: {g: i for i, g in enumerate(ordered_groups)},
            other_dim: dict(data_form.labels[other_dim]),
        }

        out_info, out_axes = metadata(data_form, [other_dim], "aggregate")
        ctx[out_name] = Form(
            data=out_data.astype(np.float32),
            dims=[group_dim, other_dim],
            labels=out_labels,
            info=out_info,
            axis_info=out_axes,
        )

        group_sizes = {}
        for g, v, gn in zip(ordered_groups, [True] * n_groups,
                            ordered_groups):
            group_sizes[g] = 0
        for g, v in zip(group_names, valid):
            if v:
                group_sizes[g] += 1

        self._export_data = {
            "dim": dim,
            "group_dim": group_dim,
            "other_dim": other_dim,
            "method": method,
            "group_col": group_col,
            "n_input_rows": len(common),
            "n_groups": n_groups,
            "n_other_features": n_other,
            "groups": ordered_groups,
            "group_sizes": group_sizes,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "method": method,
            "n_groups": n_groups,
            "n_other_features": n_other,
        }

        print(
            f"[aggregate] dim='{dim}' group_col='{group_col}' "
            f"method='{method}' {len(common)} rows -> "
            f"{n_groups} groups x {n_other} features"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
    icon = 'Stack'


def _decode(code, encoder):
    if encoder is None:
        try:
            f = float(code)
        except (TypeError, ValueError):
            return str(code)
        if not np.isfinite(f):
            return None
        return str(int(f)) if float(f).is_integer() else str(f)
    try:
        return str(encoder.inverse[int(code)])
    except (KeyError, ValueError, TypeError):
        return None
