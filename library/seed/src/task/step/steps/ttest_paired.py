"""Paired Student t-test for exactly two groups.

Groups are paired by sample order after alignment to metadata."""
from __future__ import annotations

import numpy as np
from scipy import stats
from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import grouped


class TTestPairedStep(Step):
    provider = 'operon-core'
    parameters_file = 'ttest_paired.TTestPairedStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'ttest_paired',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Paired t-test',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'feature_dim', 'default': 'feature'},
                                        {'param': 'sample_dim', 'default': 'sample'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'group_dim', 'default': 'feature'}],
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
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Paired t-test：接收 2 个输入，输出 Form；主要参数：特征维度、样本维度、分组维度、分组字段、Alternative。'}

    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        group_label = ctx.step_params["group_label"]
        columns, features, groups = grouped(data, meta, sample_dim, feature_dim, group_dim, group_label)
        if len(groups) != 2:
            raise StepError("ttest_paired needs exactly two groups")
        if len({col.shape[0] for col in columns}) != 1:
            raise StepError("ttest_paired requires equal paired group sizes")
        rows = []
        for i in range(len(features)):
            values = [col[:, i] for col in columns]
            try:
                statistic, pvalue = stats.ttest_rel(
                    values[0], values[1],
                    alternative=ctx.step_params.get("alternative", "two-sided"),
                )
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
        self._export = {"n_features": len(features), "n_groups": len(groups), "groups": groups, "method": "paired_t_test"}
        print(f"[ttest_paired] {len(features)} features, {len(groups)} groups")

    def export(self, ctx: Context) -> dict:
        return self._export
