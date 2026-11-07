"""Difference-sign test for serial randomness."""
from __future__ import annotations

import numpy as np
from scipy.stats import norm

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._timeseries63_common import numeric_series


class DifferenceSignStep(Step):
    provider = 'operon-core'
    parameters_file = 'difference_sign.DifferenceSignStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'difference_sign',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Difference-sign test',
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
     'dependencies': ['numpy>=1.24', 'scipy>=1.10'],
     'dependency_imports': ['numpy', 'scipy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Difference-sign test：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、数值字段、Alternative。'}

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        alternative = ctx.step_params.get("alternative", "two-sided")
        out_name = ctx.step_params.get("output", self.name)
        _, values = numeric_series(inputs[0], sample_dim, feature_dim, value_label, self.name)
        differences = np.diff(values)
        zeros = int(np.sum(differences == 0))
        differences = differences[differences != 0]
        if differences.size < 2:
            raise StepError("difference_sign: need at least two non-zero successive differences")
        n = int(differences.size) + 1
        positive = int(np.sum(differences > 0))
        mean = (n - 1) / 2.0
        variance = (n + 1) / 12.0
        z = float((positive - mean) / np.sqrt(variance))
        if alternative == "greater":
            p = float(norm.sf(z))
        elif alternative == "less":
            p = float(norm.cdf(z))
        else:
            p = float(2.0 * norm.sf(abs(z)))
        rows = [
            [z],
            [p],
            [float(n)],
            [float(positive)],
            [float(zeros)],
        ]
        form = Form(
            data=np.asarray(rows, dtype=np.float64),
            dims=["metric", "value"],
            labels={
                "metric": {"z": 0, "p": 1, "n": 2, "positive": 3, "zeros": 4},
                "value": {"value": 0},
            },
            info={
                "missing_code": np.nan,
                "method": "difference_sign",
                "alternative": alternative,
                "n": n,
                "zeros": zeros,
            },
        )
        ctx[out_name] = form
        self._export_data = {
            "z": z,
            "p": p,
            "n": n,
            "positive": positive,
            "zeros": zeros,
            "alternative": alternative,
        }
        print(f"[{self.name}] z={z:.4f}, n={n}, zeros={zeros}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
