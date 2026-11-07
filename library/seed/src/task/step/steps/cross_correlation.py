"""Cross-correlation function for two aligned series."""
from __future__ import annotations

import numpy as np
from scipy.stats import norm

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._timeseries63_common import aligned_series


class CrossCorrelationStep(Step):
    provider = 'operon-core'
    parameters_file = 'cross_correlation.CrossCorrelationStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'cross_correlation',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Cross-correlation function',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'feature_dim', 'default': 'feature'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
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
     'dependencies': ['numpy>=1.24', 'scipy>=1.10'],
     'dependency_imports': ['numpy', 'scipy'],
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Cross-correlation function：接收 2 个输入，输出 Form；主要参数：样本维度、特征维度、First Label、Second '
                    'Label、Lags、显著性水平。'}

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        first_label = ctx.step_params["first_label"]
        second_label = ctx.step_params["second_label"]
        lags = int(ctx.step_params.get("lags", 10))
        alpha = float(ctx.step_params.get("alpha", 0.05))
        out_name = ctx.step_params.get("output", self.name)
        x, y = aligned_series(inputs[0], inputs[1], sample_dim, feature_dim, first_label, second_label, self.name)
        n = int(x.size)
        if lags < 1:
            raise StepError("cross_correlation: lags must be at least 1")
        if lags >= n:
            raise StepError("cross_correlation: lags must be less than n")
        if float(np.var(x)) <= 0 or float(np.var(y)) <= 0:
            raise StepError("cross_correlation: both series need variation")
        mx = float(x.mean())
        my = float(y.mean())
        sx = float(x.std(ddof=0))
        sy = float(y.std(ddof=0))
        rows = []
        labels = {}
        values = []
        for lag in range(-lags, lags + 1):
            if lag >= 0:
                left = x[lag:]
                right = y[: n - lag]
            else:
                left = x[: n + lag]
                right = y[-lag:]
            ccf = float(np.sum((left - mx) * (right - my)) / (n * sx * sy))
            rows.append([ccf, -norm.ppf(1 - alpha / 2) / np.sqrt(n), norm.ppf(1 - alpha / 2) / np.sqrt(n)])
            labels[str(lag)] = lag + lags
            values.append((lag, ccf))
        form = Form(
            data=np.asarray(rows, dtype=np.float64),
            dims=["lag", "statistic"],
            labels={
                "lag": labels,
                "statistic": {"ccf": 0, "ci_lower": 1, "ci_upper": 2},
            },
            info={
                "missing_code": np.nan,
                "method": "pearson_lag_correlation",
                "n": n,
                "lags": lags,
                "alpha": alpha,
            },
        )
        ctx[out_name] = form
        self._export_data = {
            "n": n,
            "lags": lags,
            "alpha": alpha,
            "ccf": [{"lag": lag, "ccf": value} for lag, value in values],
        }
        print(f"[{self.name}] n={n}, lags={lags}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
