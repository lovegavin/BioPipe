"""Locally weighted scatterplot smoothing (LOWESS)."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame


class LowessStep(Step):
    provider = 'operon-core'
    """Cleveland's LOWESS smoother with a fixed span and robust iterations.

    The implementation delegates the local regressions to
    ``statsmodels.nonparametric.smoothers_lowess.lowess``, which matches R's
    ``stats::lowess`` for the same span and iteration count.
    """
    parameters_file = 'lowess.LowessStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'lowess',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'LOWESS smoother',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'feature_dim', 'default': 'feature'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.24', 'pandas>=2.0', 'statsmodels>=0.14'],
     'dependency_imports': ['numpy', 'pandas', 'statsmodels'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': "Cleveland's LOWESS smoother with a fixed span and robust iterations."}


    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.nonparametric.smoothers_lowess import lowess

        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        x_label = ctx.step_params["x_label"]
        y_label = ctx.step_params["y_label"]
        frac = float(ctx.step_params.get("frac", 2.0 / 3.0))
        iterations = int(ctx.step_params.get("iterations", 3))
        out_name = ctx.step_params.get("output", self.name)

        if not 0.0 < frac <= 1.0:
            raise StepError(f"{self.name}: frac must be in (0, 1]")
        if not 0 <= iterations <= 10:
            raise StepError(f"{self.name}: iterations must be in 0..10")

        frame = table_frame(form, sample_dim, feature_dim, self.name)
        x = numeric_column(frame, x_label, self.name)
        y = numeric_column(frame, y_label, self.name)
        keep = np.isfinite(x) & np.isfinite(y)
        x = x[keep]
        y = y[keep]
        samples = frame.loc[keep, "__sample__"].astype(str).to_numpy()
        if x.size < 3:
            raise StepError(f"{self.name}: need at least three complete observations")
        if np.ptp(x) <= 0:
            raise StepError(f"{self.name}: x must vary")
        order = np.argsort(x, kind="mergesort")
        x = x[order]
        y = y[order]
        samples = samples[order]
        fitted = lowess(y, x, frac=frac, it=iterations, return_sorted=False)
        fitted = np.asarray(fitted, dtype=np.float64)
        if fitted.size != x.size:
            raise StepError(f"{self.name}: smoother returned an unexpected length")
        residual = y - fitted

        ctx[out_name] = Form(
            data=np.column_stack([x, y, fitted, residual]).astype(np.float64),
            dims=["sample", "statistic"],
            labels={
                "sample": {name: i for i, name in enumerate(samples)},
                "statistic": {
                    "x": 0,
                    "y": 1,
                    "fitted": 2,
                    "residual": 3,
                },
            },
            info={
                "missing_code": np.nan,
                "method": "lowess",
                "frac": frac,
                "iterations": iterations,
                "n": int(x.size),
            },
        )
        self._export_data = {
            "x": x.tolist(),
            "y": y.tolist(),
            "fitted": fitted.tolist(),
            "residual": residual.tolist(),
            "samples": samples.tolist(),
            "frac": frac,
            "iterations": iterations,
            "n": int(x.size),
        }
        print(f"[{self.name}] n={x.size}, frac={frac:.4g}, iterations={iterations}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
