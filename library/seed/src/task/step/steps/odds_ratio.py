"""Odds ratio with a Woolf log-scale confidence interval."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step

from ._epi64_common import corrected_table, count_table, odds_ratio


class OddsRatioStep(Step):
    provider = 'operon-core'
    parameters_file = 'odds_ratio.OddsRatioStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'odds_ratio',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Odds ratio',
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
     'description': 'Odds ratio：接收 1 个输入，输出 Form；主要参数：Row Dim、Col Dim、Correction、Confidence。'}

    def run(self, ctx: Context, inputs) -> None:
        table = count_table(
            inputs[0],
            ctx.step_params.get("row_dim", "row"),
            ctx.step_params.get("col_dim", "col"),
            self.name,
        )
        table, corrected = corrected_table(
            table, ctx.step_params.get("correction", "haldane"), self.name
        )
        result = odds_ratio(table, float(ctx.step_params.get("confidence", 0.95)))
        stats = [
            result["odds_ratio"],
            result["ci_lower"],
            result["ci_upper"],
            result["log_or"],
            result["se"],
            result["n"],
        ]
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray([stats], dtype=np.float64),
            dims=["metric", "statistic"],
            labels={
                "metric": {"odds_ratio": 0},
                "statistic": {
                    "odds_ratio": 0,
                    "ci_lower": 1,
                    "ci_upper": 2,
                    "log_or": 3,
                    "se": 4,
                    "n": 5,
                },
            },
            info={"missing_code": np.nan, "correction": "haldane" if corrected else "none"},
        )
        self._export_data = {
            "odds_ratio": result["odds_ratio"],
            "ci_lower": result["ci_lower"],
            "ci_upper": result["ci_upper"],
            "log_or": result["log_or"],
            "se": result["se"],
            "n": int(result["n"]),
            "correction": "haldane" if corrected else "none",
        }
        print(f"[odds_ratio] or={result['odds_ratio']:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
