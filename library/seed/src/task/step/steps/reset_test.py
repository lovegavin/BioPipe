"""RESET functional-form test for an OLS regression."""
from __future__ import annotations

from statsmodels.stats.diagnostic import linear_reset

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._diagnostics29_common import fit_linear
from ._ext_common import make_form


class ResetTestStep(Step):
    provider = 'operon-core'
    parameters_file = 'reset_test.ResetTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'reset_test',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'RESET functional-form test',
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
     'description': 'RESET functional-form test：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、Response '
                    'Label、Predictors、分类协变量、Power。'}

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        response_label = ctx.step_params["response_label"]
        predictors = list(ctx.step_params["predictors"])
        categorical = list(ctx.step_params.get("categorical", []))
        power = int(ctx.step_params.get("power", 2))
        out_name = ctx.step_params.get("output", self.name)
        if power < 2:
            raise StepError(f"{self.name}: power must be at least 2")
        result, _, _, _ = fit_linear(
            inputs[0], sample_dim, feature_dim, response_label, predictors, categorical, self.name
        )
        test = linear_reset(result, power=power, test_type="fitted", use_f=True)
        rows = [
            ("f_statistic", float(test.statistic)),
            ("p", float(test.pvalue)),
            ("df_num", float(test.df_num)),
            ("df_denom", float(test.df_denom)),
            ("power", float(power)),
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
            "f_statistic": float(test.statistic),
            "p": float(test.pvalue),
            "df_num": int(test.df_num),
            "df_denom": int(test.df_denom),
            "power": power,
        }
        print(f"[{self.name}] F={test.statistic:.4f}, p={test.pvalue:.4g}")

    def export(self, ctx: Context) -> dict:
        return self._export
