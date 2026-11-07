"""One-sample Student t-test against a fixed population mean."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class TTestOneSampleStep(Step):
    provider = 'operon-core'
    parameters_file = 'ttest_one_sample.TTestOneSampleStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'ttest_one_sample',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'One-sample t-test',
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
     'description': 'One-sample t-test：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、Popmean、Alternative。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        X, _samples, features = matrix(form, sample_dim, feature_dim)
        popmean = float(ctx.step_params.get("popmean", 0.0))
        alternative = ctx.step_params.get("alternative", "two-sided")
        from scipy import stats

        rows = []
        for i in range(len(features)):
            try:
                statistic, pvalue = stats.ttest_1samp(X[:, i], popmean, alternative=alternative, nan_policy="omit")
            except ValueError:
                statistic, pvalue = float("nan"), float("nan")
            rows.append([float(statistic), float(pvalue)])
        block = np.asarray(rows, dtype=np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=block,
            dims=[feature_dim, "statistic"],
            labels={
                feature_dim: {name: i for i, name in enumerate(features)},
                "statistic": {"T": 0, "P": 1},
            },
            info={"missing_code": np.nan},
        )
        self._export = {"n_features": len(features), "popmean": popmean, "method": "one_sample_t_test"}
        print(f"[ttest_one_sample] {len(features)} features")

    def export(self, ctx: Context) -> dict:
        return self._export
