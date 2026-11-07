"""Bartels rank test for randomness."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class BartelsRankStep(Step):
    provider = 'operon-core'
    """Bartels rank von Neumann ratio test, normal approximation."""
    parameters_file = 'bartels_rank.BartelsRankStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'bartels_rank',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Bartels rank test',
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
     'description': 'Bartels rank von Neumann ratio test, normal approximation.'}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, "bartels_rank")
        values = numeric_column(frame, value_label, "bartels_rank")
        values = values[np.isfinite(values)]
        n = int(values.size)
        if n < 10:
            raise StepError("bartels_rank: sample size must be at least 10")
        ranks = stats.rankdata(values, method="average")
        diffs = np.diff(ranks)
        sum_d2 = float(np.sum(diffs * diffs))
        denom = float(np.sum(ranks * ranks) - n * np.mean(ranks) ** 2)
        if denom <= 0 or not np.isfinite(denom):
            raise StepError("bartels_rank: ranks have zero variance")
        rvn = sum_d2 / denom
        mu = 2.0
        var = (4.0 * (n - 2.0) * (5.0 * n * n - 2.0 * n - 9.0)) / (
            5.0 * n * (n + 1.0) * (n - 1.0) ** 2
        )
        if var <= 0:
            raise StepError("bartels_rank: test variance is zero")
        z_value = float((rvn - mu) / np.sqrt(var))
        p_value = float(2.0 * stats.norm.sf(abs(z_value)))
        out = scalar_form(
            [rvn, z_value, mu, var, p_value, float(n), sum_d2],
            ["RVN", "z", "mu", "var", "p", "n", "sum_d2"],
            "bartels_rank",
        )
        out.info.update({"alternative": "nonrandomness", "p_method": "normal"})
        ctx[out_name] = out
        self._export_data = {
            "RVN": rvn, "z": z_value, "mu": mu, "var": var, "p": p_value,
            "n": n, "sum_d2": sum_d2,
        }
        print(f"[bartels_rank] RVN={rvn:.6f}, z={z_value:.6f}, p={p_value:.6g}, n={n}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
