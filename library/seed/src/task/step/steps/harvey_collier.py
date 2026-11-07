"""Harvey-Collier linearity test for an OLS regression."""
from __future__ import annotations

from statsmodels.stats.diagnostic import linear_harvey_collier

from src.task.context import Context
from src.task.step.base import Step

from ._diagnostics29_common import fit_linear
from ._ext_common import make_form


class HarveyCollierStep(Step):
    provider = 'operon-core'
    parameters_file = 'harvey_collier.HarveyCollierStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'harvey_collier',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Harvey-Collier linearity test',
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
                                         'info_open': False,
                                         'axis_info_open': False,
                                         'info': {'missing_code': {'type': ['number', 'null']}}}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Harvey-Collier linearity test：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、Response '
                    'Label、Predictors、分类协变量。'}

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response_label = ctx.step_params["response_label"]
        predictors = list(ctx.step_params["predictors"])
        categorical = list(ctx.step_params.get("categorical", []))
        out_name = ctx.step_params.get("output", self.name)
        result, _, _, _ = fit_linear(
            inputs[0], sample_dim, feature_dim, response_label, predictors, categorical, self.name
        )
        test = linear_harvey_collier(result)
        rows = [
            ("statistic", float(test.statistic)),
            ("p", float(test.pvalue)),
            ("df", float(test.df)),
        ]
        ctx[out_name] = make_form(
            [[value] for _, value in rows],
            ["statistic", "value"],
            {
                "statistic": {name: i for i, (name, _) in enumerate(rows)},
                "value": {"value": 0},
            },
        )
        self._export = {
            "statistic": float(test.statistic),
            "p": float(test.pvalue),
            "df": int(test.df),
        }
        print(f"[{self.name}] t={test.statistic:.4f}, p={test.pvalue:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export
