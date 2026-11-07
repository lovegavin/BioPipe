"""Pearson chi-square test for a contingency table."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class ChiSquareStep(Step):
    provider = 'operon-core'
    parameters_file = 'chi_square.ChiSquareStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'chi_square',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Chi-square test',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'row_dim', 'default': 'row'},
                                        {'param': 'col_dim', 'default': 'col'}],
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
     'description': 'Chi-square test：接收 1 个输入，输出 Form；主要参数：Row Dim、Col Dim、Correction。'}

    def run(self, ctx: Context, inputs) -> None:
        table = np.asarray(inputs[0].data, dtype=np.float64)
        if table.ndim != 2 or min(table.shape) < 2:
            raise StepError("chi_square needs a 2D table with at least 2 rows and 2 columns")
        if (table < 0).any():
            raise StepError("chi_square requires non-negative counts")
        chi2, p, dof, _expected = stats.chi2_contingency(
            table, correction=bool(ctx.step_params.get("correction", True))
        )
        n = float(table.sum())
        cramers_v = float(np.sqrt(chi2 / (n * (min(table.shape) - 1)))) if n > 0 else float("nan")
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray([[chi2, p, dof, cramers_v]], dtype=np.float32),
            dims=["metric", "statistic"],
            labels={"metric": {"chi_square": 0}, "statistic": {"chi2": 0, "P": 1, "dof": 2, "cramers_v": 3}},
            info={"missing_code": np.nan},
        )
        self._export_data = {"chi2": float(chi2), "p": float(p), "dof": int(dof), "cramers_v": cramers_v}
        print(f"[chi_square] chi2={chi2:.3f}, p={p:.3g}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
