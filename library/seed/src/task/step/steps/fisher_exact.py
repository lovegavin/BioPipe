"""Fisher exact test for a 2x2 contingency table."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class FisherExactStep(Step):
    provider = 'operon-core'
    parameters_file = 'fisher_exact.FisherExactStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'fisher_exact',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Fisher exact test',
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
     'description': 'Fisher exact test：接收 1 个输入，输出 Form；主要参数：Row Dim、Col Dim、Alternative。'}

    def run(self, ctx: Context, inputs) -> None:
        table = np.asarray(inputs[0].data, dtype=np.float64)
        if table.shape != (2, 2):
            raise StepError(f"fisher_exact needs a 2x2 table, got {table.shape}")
        if (table < 0).any():
            raise StepError("fisher_exact requires non-negative counts")
        odds, p = stats.fisher_exact(table, alternative=ctx.step_params.get("alternative", "two-sided"))
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray([[odds, p]], dtype=np.float32),
            dims=["metric", "statistic"],
            labels={"metric": {"fisher_exact": 0}, "statistic": {"odds_ratio": 0, "P": 1}},
            info={"missing_code": np.nan},
        )
        self._export_data = {"odds_ratio": float(odds), "p": float(p)}
        print(f"[fisher_exact] odds_ratio={odds:.3f}, p={p:.3g}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
