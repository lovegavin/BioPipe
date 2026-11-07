"""Shapiro-Wilk normality test."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class ShapiroWilkStep(Step):
    provider = 'operon-core'
    """Shapiro-Wilk W test for univariate normality."""
    parameters_file = 'shapiro_wilk.ShapiroWilkStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'shapiro_wilk',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Shapiro-Wilk normality test',
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
     'dependencies': ['scipy>=1.11'],
     'dependency_imports': ['scipy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Shapiro-Wilk W test for univariate normality.'}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, "shapiro_wilk")
        values = numeric_column(frame, value_label, "shapiro_wilk")
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 3 or n > 5000:
            raise StepError("shapiro_wilk: sample size must be between 3 and 5000")
        if float(np.var(values)) <= 0:
            raise StepError("shapiro_wilk: values have zero variance")
        result = stats.shapiro(values)
        w = float(result.statistic)
        p_value = float(result.pvalue)
        out = scalar_form([w, p_value, float(n)], ["W", "p", "n"], "shapiro_wilk")
        out.info.update({"method": "shapiro-wilk", "approximation": "AS R94"})
        ctx[out_name] = out
        self._export_data = {"W": w, "p": p_value, "n": n}
        print(f"[shapiro_wilk] W={w:.8f}, p={p_value:.6g}, n={n}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
