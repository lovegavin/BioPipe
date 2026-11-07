"""Classical seasonal decomposition with centered moving averages.

Additive or multiplicative decomposition of one numeric series into
observed, trend, seasonal and residual components, matching
``statsmodels.tsa.seasonal.seasonal_decompose`` and R ``stats::decompose``
(two-sided centered moving average; seasonal means are centered to sum to
zero for the additive model and to mean one for the multiplicative model).

The series is read from one numeric column of a ``[sample, feature]``
table. Trend and residual endpoints are NaN because the centered moving
average is undefined there.
"""
from __future__ import annotations

import numpy as np
from statsmodels.tsa.seasonal import seasonal_decompose

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame


class SeasonalDecomposeStep(Step):
    provider = 'operon-core'
    parameters_file = 'seasonal_decompose.SeasonalDecomposeStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
                  'id': 'seasonal_decompose',
                  'version': '1.0.0',
                  'kind': 'operator',
                  'title': 'Classical seasonal decomposition',
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
                  'resources': {'memory_modes': ['full'],
                                'supports_cuda': False,
                                'estimate': 'estimate_memory'},
                  'dependencies': ['statsmodels>=0.14'],
                  'dependency_imports': ['statsmodels'],
                  'inputs_arity': 1,
                  'outputs': [],
                  'output_parameter': 'output',
                  'description': 'Classical moving-average seasonal decomposition (additive or multiplicative).'}

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        period = int(ctx.step_params["period"])
        model = str(ctx.step_params.get("model", "additive"))
        two_sided = bool(ctx.step_params.get("two_sided", True))
        out_name = ctx.step_params.get("output", self.name)

        if period < 2:
            raise StepError("seasonal_decompose: period must be at least 2")
        if model not in ("additive", "multiplicative"):
            raise StepError(
                "seasonal_decompose: model must be 'additive' or 'multiplicative'"
            )

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        values = numeric_column(frame, value_label, self.name)
        n = int(values.size)
        if n < 2 * period:
            raise StepError(
                f"seasonal_decompose: series has {n} points, need at least "
                f"{2 * period} (two full periods)"
            )
        if not np.all(np.isfinite(values)):
            raise StepError(
                "seasonal_decompose: series contains missing or non-finite values"
            )
        if model == "multiplicative" and np.any(values <= 0):
            raise StepError(
                "seasonal_decompose: multiplicative model requires strictly "
                "positive values"
            )

        result = seasonal_decompose(
            values,
            model=model,
            period=period,
            two_sided=two_sided,
            extrapolate_trend=0,
        )
        rows = np.column_stack([
            values,
            np.asarray(result.trend, dtype=np.float64),
            np.asarray(result.seasonal, dtype=np.float64),
            np.asarray(result.resid, dtype=np.float64),
        ])
        form = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["time", "statistic"],
            labels={
                "time": {str(i): i for i in range(n)},
                "statistic": {"observed": 0, "trend": 1,
                              "seasonal": 2, "resid": 3},
            },
            info={
                "missing_code": np.nan,
                "period": period,
                "model": model,
                "two_sided": two_sided,
                "n": n,
            },
        )
        ctx[out_name] = form
        self._export_data = {
            "period": period,
            "model": model,
            "two_sided": two_sided,
            "n": n,
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
