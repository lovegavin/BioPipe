"""Cohen's kappa for two raters on a contingency table."""
from __future__ import annotations

import numpy as np
from statsmodels.stats.inter_rater import cohens_kappa

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._stats20_common import scalar_form, table


_NAMES = ["kappa", "std_kappa", "z", "p", "ci_low", "ci_high"]


class CohensKappaStep(Step):
    provider = 'operon-core'
    parameters_file = 'cohens_kappa.CohensKappaStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'cohens_kappa',
     'version': '1.0.0',
     'kind': 'operator',
     'title': "Cohen's kappa",
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'row_dim', 'default': 'rater_a'},
                                        {'param': 'col_dim', 'default': 'rater_b'}],
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
     'description': "Cohen's kappa：接收 1 个输入，输出 Form；主要参数：Row Dim、Col Dim、Weights。"}

    def run(self, ctx: Context, inputs) -> None:
        data, rows, cols = table(
            inputs[0], ctx.step_params.get("row_dim", "rater_a"),
            ctx.step_params.get("col_dim", "rater_b"), "cohens_kappa",
        )
        if np.any(data < 0):
            raise StepError("cohens_kappa: cell counts must be non-negative")
        weights = ctx.step_params.get("weights", "none")
        result = cohens_kappa(
            data,
            weights=None if weights == "none" else weights,
            return_results=True,
        )
        rows_out = [
            result.kappa, result.std_kappa, result.z_value, result.pvalue_two_sided,
            result.kappa_low, result.kappa_upp,
        ]
        form = scalar_form(rows_out, _NAMES, "cohens_kappa")
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export = {
            "kappa": float(result.kappa),
            "p": float(result.pvalue_two_sided),
            "weights": weights,
            "n_categories": int(data.shape[0]),
        }
        print(f"[cohens_kappa] kappa={result.kappa:.6g} p={result.pvalue_two_sided:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
