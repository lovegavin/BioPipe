"""Cohen's h effect size for two independent proportions."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._epi64_common import cohens_h, count_table


class CohensHStep(Step):
    provider = 'operon-core'
    parameters_file = 'cohens_h.CohensHStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'cohens_h',
     'version': '1.0.0',
     'kind': 'operator',
     'title': "Cohen's h",
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
     'description': "Cohen's h：接收 1 个输入，输出 Form；主要参数：Row Dim、Col Dim、Confidence。"}

    def run(self, ctx: Context, inputs) -> None:
        table = count_table(
            inputs[0],
            ctx.step_params.get("row_dim", "row"),
            ctx.step_params.get("col_dim", "col"),
            self.name,
        )
        result = cohens_h(table, float(ctx.step_params.get("confidence", 0.95)))
        stats = [
            result["h"],
            result["ci_lower"],
            result["ci_upper"],
            result["p1"],
            result["p2"],
            result["n1"],
            result["n2"],
        ]
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray([stats], dtype=np.float64),
            dims=["metric", "statistic"],
            labels={
                "metric": {"cohens_h": 0},
                "statistic": {
                    "cohens_h": 0,
                    "ci_lower": 1,
                    "ci_upper": 2,
                    "p1": 3,
                    "p2": 4,
                    "n1": 5,
                    "n2": 6,
                },
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {
            "cohens_h": result["h"],
            "ci_lower": result["ci_lower"],
            "ci_upper": result["ci_upper"],
            "p1": result["p1"],
            "p2": result["p2"],
            "n1": int(result["n1"]),
            "n2": int(result["n2"]),
        }
        print(f"[cohens_h] h={result['h']:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
