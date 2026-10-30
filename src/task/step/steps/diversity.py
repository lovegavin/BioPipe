# src/task/step/steps/diversity.py
"""Diversity metrics along one axis of a form.

Reduce ``dim`` into one or more diversity metrics, preserving every other
axis. The output replaces the reduced axis with a final ``metric`` axis.

Metrics
-------
    shannon        Shannon entropy H = -sum(p_i * log(p_i))
    simpson        Gini-Simpson index 1 - sum(p_i^2)
    richness       number of non-zero values
    evenness       Shannon / log(richness)
    gini           Gini coefficient of the distribution

Where p_i = v_i / sum(v) is the relative abundance of the i-th
position along the other axis. Non-finite values are dropped before
computing p; a position whose total is zero yields NaN for every
metric that requires proportions.

Axis-parallel info on the reduced dim is dropped from the output.
Info for surviving dims passes through. ``info["encoders"]`` is
trimmed to surviving dims.

Params:
    dim      : dimension to compute metrics along (required)
    metrics  : metric name, or list of names (required)
    output   : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._microbiome import estimate, metadata


_METRICS = ("shannon", "simpson", "richness", "evenness", "gini")


class DiversityStep(Step):
    """Compute diversity metrics along one axis."""
    provider = 'biopipe-microbiome'
    parameters_file = 'diversity.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'diversity',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Alpha diversity',
     'description': 'Compute diversity metrics along one axis.',
     'category': '统计分析',
     'icon': 'CirclesThree',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'dim', 'default': None}],
                               'labels': [],
                               'parallel': []}],
                   'output': {'mode': 'project',
                              'derived': True,
                              'info': {'missing_code': {'type': ['number', 'null']},
                                       'representation': {'type': 'string', 'const': 'diversity'}},
                              'drop_dims': [{'param': 'dim', 'default': None}],
                              'append_dims': [{'name': 'metric',
                                               'labels': {'param': 'metrics', 'default': None}}]}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output'}



    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return estimate(cls.name, inputs, params, profiles)

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params.get("dim")
        metrics = ctx.step_params.get("metrics")
        out_name = ctx.step_params.get("output", self.name)

        if not dim:
            raise StepError("diversity: 'dim' is required")
        if dim not in form.dims:
            raise StepError(
                f"diversity: dim '{dim}' not present. "
                f"Available: {form.dims}"
            )
        if isinstance(metrics, str):
            metrics = [metrics]
        if not isinstance(metrics, list) or not metrics:
            raise StepError(
                "diversity: 'metrics' must be a non-empty list"
            )
        for m in metrics:
            if m not in _METRICS:
                raise StepError(
                    f"diversity: unknown metric '{m}'. "
                    f"Known: {list(_METRICS)}"
                )
        if len(set(metrics)) != len(metrics):
            raise StepError(
                f"diversity: duplicate metric names: {metrics}"
            )

        axis = form.dims.index(dim)
        data = form.data.astype(np.float64)

        missing_code = form.info.get("missing_code", np.nan)
        if isinstance(missing_code, float) and np.isnan(missing_code):
            missing = np.isnan(data)
        else:
            missing = data == missing_code

        # Move the reduced axis to the last position so that each row
        # of the flattened array is one observation along the
        # surviving axes.
        moved = np.moveaxis(data, axis, -1)
        moved_missing = np.moveaxis(missing, axis, -1)
        original_shape = moved.shape
        n_reduced = original_shape[-1]
        flat = moved.reshape(-1, n_reduced)
        flat_missing = moved_missing.reshape(-1, n_reduced)
        valid = ~flat_missing & np.isfinite(flat)
        if (flat[valid] < 0).any():
            raise StepError("diversity: abundance values must be non-negative")

        masked = np.where(valid, flat, np.nan)
        totals = np.nansum(masked, axis=1)

        computed = [
            _compute_metric(name, masked, totals, valid)
            for name in metrics
        ]
        stacked = np.stack(computed, axis=1).astype(np.float32)

        out_dims = [d for d in form.dims if d != dim] + ["metric"]
        out_labels = {
            d: dict(form.labels[d]) for d in form.dims if d != dim
        }
        out_labels["metric"] = {
            m: i for i, m in enumerate(metrics)
        }

        out_info, out_axis_info = metadata(form, out_dims[:-1], "diversity")
        stacked = stacked.reshape(original_shape[:-1] + (len(metrics),))

        ctx[out_name] = Form(
            data=stacked,
            dims=out_dims,
            labels=out_labels,
            info=out_info,
            axis_info=out_axis_info,
        )

        self._export_data = {
            "dim": dim,
            "metrics": list(metrics),
            "input_dims": list(form.dims),
            "input_shape": list(form.data.shape),
            "output_dims": out_dims,
            "output_shape": list(stacked.shape),
            "n_reduced": int(n_reduced),
            "n_rows": int(stacked.shape[0]),
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "metrics": list(metrics),
            "n_reduced": int(n_reduced),
            "n_rows": int(stacked.shape[0]),
        }

        print(
            f"[diversity] dim='{dim}' metrics={list(metrics)} "
            f"{form.data.shape} -> {stacked.shape}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _compute_metric(name, masked, totals, valid):
    with np.errstate(invalid="ignore", divide="ignore"):
        if name == "richness":
            return (valid & (masked > 0)).sum(axis=1).astype(np.float64)

        if name == "shannon":
            safe_totals = np.where(
                (totals > 0) & np.isfinite(totals), totals, np.nan
            )
            p = masked / safe_totals[:, None]
            log_p = np.where(p > 0, np.log(np.where(p > 0, p, 1.0)), 0.0)
            H = -np.nansum(np.where(p > 0, p * log_p, 0.0), axis=1)
            return np.where(np.isfinite(safe_totals), H, np.nan)

        if name == "simpson":
            safe_totals = np.where(
                (totals > 0) & np.isfinite(totals), totals, np.nan
            )
            p = masked / safe_totals[:, None]
            S = 1.0 - np.nansum(
                np.where(np.isfinite(p), p ** 2, 0.0), axis=1
            )
            return np.where(np.isfinite(safe_totals), S, np.nan)

        if name == "evenness":
            safe_totals = np.where(
                (totals > 0) & np.isfinite(totals), totals, np.nan
            )
            p = masked / safe_totals[:, None]
            log_p = np.where(p > 0, np.log(np.where(p > 0, p, 1.0)), 0.0)
            H = -np.nansum(np.where(p > 0, p * log_p, 0.0), axis=1)
            S = (valid & (masked > 0)).sum(axis=1).astype(np.float64)
            with np.errstate(invalid="ignore", divide="ignore"):
                e = np.where(S > 1, H / np.log(S), np.nan)
            return np.where(np.isfinite(safe_totals), e, np.nan)

        if name == "gini":
            sorted_vals = np.sort(
                np.where(valid, masked, np.inf), axis=1
            )
            sorted_vals = np.where(np.isfinite(sorted_vals), sorted_vals, 0.0)
            n = valid.sum(axis=1).astype(np.float64)
            g = (
                (2.0 * np.arange(1, sorted_vals.shape[1] + 1)
                 - n[:, None] - 1)
                * sorted_vals
            ).sum(axis=1)
            denom = n * sorted_vals.sum(axis=1)
            return np.where(denom > 0, g / denom, np.nan)

    raise StepError(f"diversity: no implementation for '{name}'")
