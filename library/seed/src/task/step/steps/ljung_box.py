"""Ljung-Box autocorrelation test for a univariate series."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class LjungBoxStep(Step):
    provider = 'operon-core'
    parameters_file = 'ljung_box.LjungBoxStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'ljung_box',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Ljung-Box autocorrelation test',
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
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Ljung-Box autocorrelation test：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、数值字段、Lags。'}

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        lags = int(ctx.step_params.get("lags", 10))
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        values = numeric_column(frame, value_label, self.name)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if lags < 1:
            raise StepError("ljung_box: lags must be at least 1")
        if lags >= n - 1:
            raise StepError("ljung_box: lags must be less than n - 1")
        centered = values - values.mean()
        denom = float(np.sum(centered * centered))
        if denom <= 0:
            raise StepError("ljung_box: series has no variation")
        q = 0.0
        for lag in range(1, lags + 1):
            r = float(np.sum(centered[lag:] * centered[:-lag]) / denom)
            q += r * r / (n - lag)
        q *= n * (n + 2)
        p = float(stats.chi2.sf(q, lags))
        vals = [("Q", q), ("df", float(lags)), ("p", p), ("n", float(n)), ("lags", float(lags))]
        ctx[out_name] = scalar_form([value for _, value in vals], [name for name, _ in vals], "ljung_box")
        self._export = {"Q": q, "df": lags, "p": p, "n": n, "lags": lags}
        print(f"[{self.name}] Q={q:.4f}, df={lags}, p={p:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export
