"""Shapiro-Francia normality test."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class ShapiroFranciaStep(Step):
    provider = 'operon-core'
    """Shapiro-Francia W test with the standard normalizing approximation."""
    parameters_file = 'shapiro_francia.ShapiroFranciaStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'shapiro_francia',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Shapiro-Francia normality test',
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
     'description': 'Shapiro-Francia W test with the standard normalizing approximation.'}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, "shapiro_francia")
        values = numeric_column(frame, value_label, "shapiro_francia")
        values = np.sort(values[np.isfinite(values)])
        n = int(values.size)
        if n < 5 or n > 5000:
            raise StepError("shapiro_francia: sample size must be between 5 and 5000")
        if float(np.var(values)) <= 0:
            raise StepError("shapiro_francia: values have zero variance")
        # R ppoints(n, a = 3/8), the convention used by DescTools.
        quantiles = stats.norm.ppf((np.arange(1, n + 1) - 0.375) / (n + 0.25))
        correlation = float(np.corrcoef(values, quantiles)[0, 1])
        w = correlation * correlation
        u = np.log(n)
        v = np.log(u)
        mu = -1.2725 + 1.0521 * (v - u)
        sigma = 1.0308 - 0.26758 * (v + 2.0 / u)
        z_value = float((np.log(1.0 - w) - mu) / sigma)
        p_value = float(stats.norm.sf(z_value))
        out = scalar_form([w, z_value, p_value, float(n)], ["W", "z", "p", "n"], "shapiro_francia")
        out.info.update({"method": "shapiro-francia", "ppoints_a": 0.375})
        ctx[out_name] = out
        self._export_data = {"W": w, "z": z_value, "p": p_value, "n": n}
        print(f"[shapiro_francia] W={w:.8f}, z={z_value:.6f}, p={p_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
