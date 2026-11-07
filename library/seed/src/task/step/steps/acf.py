"""Autocorrelation function for a univariate series."""
from __future__ import annotations

import numpy as np
from statsmodels.tsa.stattools import acf

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame


class AcfStep(Step):
    provider = 'operon-core'
    parameters_file = 'acf.AcfStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'acf',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Autocorrelation function',
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
     'dependencies': ['statsmodels>=0.14'],
     'dependency_imports': ['statsmodels'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Autocorrelation function：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、数值字段、Lags、显著性水平。'}

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        lags = int(ctx.step_params.get("lags", 10))
        alpha = float(ctx.step_params.get("alpha", 0.05))
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        values = numeric_column(frame, value_label, self.name)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if lags < 1:
            raise StepError("acf: lags must be at least 1")
        if lags >= n:
            raise StepError("acf: lags must be less than n")
        values = values - values.mean()
        if float(np.sum(values * values)) <= 0:
            raise StepError("acf: series has no variation")
        values = values + 0.0
        estimate, confint = acf(
            values,
            nlags=lags,
            fft=False,
            alpha=alpha,
            bartlett_confint=True,
        )
        rows = []
        labels = {}
        for lag in range(lags + 1):
            rows.append([float(estimate[lag]), float(confint[lag, 0]), float(confint[lag, 1])])
            labels[str(lag)] = lag
        form = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["lag", "statistic"],
            labels={"lag": labels, "statistic": {"acf": 0, "ci_lower": 1, "ci_upper": 2}},
            info={
                "missing_code": np.nan,
                "method": "statsmodels_acf",
                "alpha": alpha,
                "n": n,
            },
        )
        ctx[out_name] = form
        self._export_data = {
            "n": n,
            "lags": lags,
            "alpha": alpha,
            "acf": [float(v) for v in estimate],
        }
        print(f"[{self.name}] n={n}, lags={lags}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
