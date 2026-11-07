"""Bonett-Seier test for Geary kurtosis."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class BonettSeierStep(Step):
    provider = 'operon-core'
    """Bonett-Seier test that Geary kurtosis equals sqrt(2/pi)."""
    parameters_file = 'bonett_seier.BonettSeierStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'bonett_seier',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Bonett-Seier Geary kurtosis test',
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
     'description': 'Bonett-Seier test that Geary kurtosis equals sqrt(2/pi).'}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        alternative = ctx.step_params.get("alternative", "two-sided")
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, self.name)
        values = numeric_column(frame, value_label, self.name)
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 3:
            raise StepError("bonett_seier: sample size must be at least 3")
        centered = values - float(values.mean())
        rho = float(np.sqrt(np.mean(centered * centered)))
        tau = float(np.mean(np.abs(centered)))
        if rho <= 0 or tau <= 0:
            raise StepError("bonett_seier: values have zero variance")
        omega = 13.29 * (np.log(rho) - np.log(tau))
        z = float(np.sqrt(n + 2.0) * (omega - 3.0) / 3.54)
        if alternative == "greater":
            p_value = float(stats.norm.sf(z))
        elif alternative == "less":
            p_value = float(stats.norm.cdf(z))
        else:
            p_value = 2.0 * float(stats.norm.sf(z))
            if p_value > 1.0:
                p_value = 2.0 - p_value
        out = scalar_form([tau, z, p_value, float(n)], ["tau", "z", "p", "n"], self.name)
        out.info.update({"alternative": alternative, "method": "Bonett-Seier Geary kurtosis"})
        ctx[out_name] = out
        self._export_data = {
            "tau": tau,
            "z": z,
            "p": p_value,
            "n": n,
            "alternative": alternative,
        }
        print(f"[{self.name}] tau={tau:.6f}, z={z:.6f}, p={p_value:.6g}, n={n}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
