"""Fleiss' kappa for several raters on a subject x category count table."""
from __future__ import annotations

import numpy as np
from statsmodels.stats.inter_rater import fleiss_kappa

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step
from ._stats20_common import scalar_form, table


class FleissKappaStep(Step):
    provider = 'biopipe-core'
    parameters_file = 'fleiss_kappa.FleissKappaStep.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'fleiss_kappa',
     'version': '1.0.0',
     'kind': 'operator',
     'title': "Fleiss' kappa",
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'subject_dim', 'default': 'subject'},
                                        {'param': 'category_dim', 'default': 'category'}],
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
     'description': "Fleiss' kappa：接收 1 个输入，输出 Form；主要参数：Subject Dim、Category Dim、方法。"}

    def run(self, ctx: Context, inputs) -> None:
        data, subjects, categories = table(
            inputs[0], ctx.step_params.get("subject_dim", "subject"),
            ctx.step_params.get("category_dim", "category"), "fleiss_kappa",
        )
        if np.any(data < 0):
            raise StepError("fleiss_kappa: cell counts must be non-negative")
        method = ctx.step_params.get("method", "fleiss")
        kappa = float(fleiss_kappa(data, method=method))
        form = scalar_form([kappa, len(subjects), len(categories)],
                           ["kappa", "n_subjects", "n_categories"], "fleiss_kappa")
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export = {"kappa": kappa, "method": method,
                        "n_subjects": len(subjects), "n_categories": len(categories)}
        print(f"[fleiss_kappa] kappa={kappa:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
