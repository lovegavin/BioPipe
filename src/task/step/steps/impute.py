# src/task/step/steps/impute.py
"""Impute missing values in a form.

Fills missing cells using a simple strategy. Common in proteomics
and metabolomics, where missing values are frequent (low-abundance
features fall below the detection limit).

Methods
-------
    min     replace every missing cell with (global minimum *
            ``min_scale``). This is the Perseus "replace by minimum"
            strategy.
    median  replace each missing cell with the median of its feature,
            computed over all other axes.
    mean    replace each missing cell with the mean of its feature,
            computed over all other axes.

The ``dim`` parameter names the feature axis. For ``median`` and
``mean``, the statistic is computed over every axis except ``dim``.
For ``min``, the statistic is the global minimum over the whole
matrix.

The operator works on any dimensionality >= 1. ``median`` and
``mean`` require at least one axis besides ``dim`` to aggregate
over; for 1D input, use ``method="min"``.

Missing cells are identified via ``info["missing_code"]`` when set
and finite, otherwise via NaN. The output has the same dims, labels,
info and axis_info as the input; only ``data`` is replaced.

Params:
    method     : "min" | "median" | "mean" (required)
    dim        : feature dim (required)
    min_scale  : multiplier for the min method (default 1.0)
    output     : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.core.contracts import port, param
from src.core.forms.metadata import project_metadata


_METHODS = ("min", "median", "mean")


class ImputeStep(Step):
    """Fill missing values in a form."""
    parameters_schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema',
     'type': 'object',
     'properties': {'method': {'title': '方法', 'enum': ['min', 'median', 'mean'], 'x-ui-default': 'median'},
                    'dim': {'title': '分析维度', 'type': 'string', 'x-ui-default': 'feature'},
                    'min_scale': {'title': '最小值倍率', 'type': 'number', 'minimum': 0, 'default': 1.0}},
     'additionalProperties': True,
     'required': ['method', 'dim']}
    title = '缺失值填补'
    category = '数据整理'
    icon = 'PuzzlePiece'
    description = '以 Min、Median 或 Mean 填补缺失'

    name = "impute"
    inputs_arity = 1
    outputs = []
    input_contracts = [port(dims=[param("dim")])]
    output_contract = {"mode": "transform", "representation": "impute"}
    output_parameter = "output"

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        method = ctx.step_params.get("method")
        dim = ctx.step_params.get("dim")
        min_scale = float(ctx.step_params.get("min_scale", 1.0))
        out_name = ctx.step_params.get("output", self.name)

        if method not in _METHODS:
            raise StepError(
                f"impute: method must be one of {_METHODS}, "
                f"got {method!r}"
            )
        if dim is None:
            raise StepError("impute: 'dim' is required")
        if dim not in form.dims:
            raise StepError(
                f"impute: dim '{dim}' not present. "
                f"Available: {form.dims}"
            )
        if form.data.ndim < 1:
            raise StepError(
                "impute: input must have at least 1 dim"
            )
        if method == "min" and min_scale <= 0:
            raise StepError(
                f"impute: min_scale must be > 0, got {min_scale}"
            )

        axis = form.dims.index(dim)
        other_axes = tuple(
            i for i in range(form.data.ndim) if i != axis
        )
        if method in ("median", "mean") and not other_axes:
            raise StepError(
                f"impute/{method}: needs at least one axis besides "
                f"'{dim}' to compute a per-feature statistic. "
                f"Use method='min' for 1D input."
            )

        data = form.data.astype(np.float64)
        missing = _missing_mask(
            data, form.info.get("missing_code", np.nan)
        )

        n_total = int(data.size)
        n_missing = int(missing.sum())

        pos_to_label = {v: k for k, v in form.labels[dim].items()}
        n_features = data.shape[axis]

        fill_value = None
        per_feature_fill = None
        all_missing_features: list[str] = []

        if n_missing == 0:
            filled = data
        elif method == "min":
            finite = data[~missing]
            if finite.size == 0:
                raise StepError(
                    "impute/min: no finite values to base the "
                    "minimum on"
                )
            fill_value = float(finite.min()) * min_scale
            filled = np.where(missing, fill_value, data)
        else:
            masked = np.where(missing, np.nan, data)
            with np.errstate(invalid="ignore"):
                if method == "median":
                    stats = np.nanmedian(masked, axis=other_axes)
                else:
                    stats = np.nanmean(masked, axis=other_axes)
            stats = np.atleast_1d(stats)

            if stats.shape[0] != n_features:
                raise StepError(
                    f"impute/{method}: unexpected statistic shape "
                    f"{stats.shape}, expected ({n_features},)"
                )

            # Features that are entirely missing fall back to the
            # global statistic and are reported in the export.
            bad = ~np.isfinite(stats)
            if bad.any():
                finite_all = masked[~missing]
                if finite_all.size == 0:
                    raise StepError(
                        f"impute/{method}: no finite values anywhere"
                    )
                if method == "median":
                    fallback = float(np.median(finite_all))
                else:
                    fallback = float(np.mean(finite_all))
                stats = np.where(bad, fallback, stats)
                all_missing_features = [
                    pos_to_label.get(int(i), f"#{i}")
                    for i in np.where(bad)[0]
                ]

            shape = [1] * data.ndim
            shape[axis] = n_features
            filled = np.where(missing, stats.reshape(shape), data)

            per_feature_fill = {
                pos_to_label.get(i, f"#{i}"): float(stats[i])
                for i in range(n_features)
            }

        result = filled.astype(np.float32)

        info, axis_info = project_metadata(form, derived=True)
        info.update(missing_code=np.nan, representation="impute")
        ctx[out_name] = Form(
            data=result,
            dims=list(form.dims),
            labels={k: dict(v) for k, v in form.labels.items()},
            info=info,
            axis_info=axis_info,
        )

        self._export_data = {
            "method": method,
            "dim": dim,
            "min_scale": min_scale if method == "min" else None,
            "n_total": n_total,
            "n_missing_before": n_missing,
            "n_imputed": n_missing,
            "fill_value": fill_value,
            "per_feature_fill": per_feature_fill,
            "all_missing_features": all_missing_features,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "method": method,
            "dim": dim,
            "n_imputed": n_missing,
        }

        if n_missing == 0:
            print(
                f"[impute] method='{method}' dim='{dim}' "
                f"no missing values to fill"
            )
        elif method == "min":
            print(
                f"[impute] method='min' dim='{dim}' "
                f"filled {n_missing} cells with {fill_value:.4g}"
            )
        else:
            print(
                f"[impute] method='{method}' dim='{dim}' "
                f"filled {n_missing} cells "
                f"({n_features} features, "
                f"{len(all_missing_features)} fully missing)"
            )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _missing_mask(data: np.ndarray, code) -> np.ndarray:
    if code is None:
        return np.isnan(data)
    if isinstance(code, float) and np.isnan(code):
        return np.isnan(data)
    return data == code