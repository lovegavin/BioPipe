"""Bonferroni multiple-testing correction.

Reads a feature x statistic table with one p-value column and writes
a feature x statistic table containing only qvalues. Bonferroni qvalues
are min(p * m, 1), where m is the number of finite p-values.
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class BonferroniStep(Step):
    provider = 'operon-core'
    parameters_file = 'bonferroni.BonferroniStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'bonferroni',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Bonferroni correction',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'feature_dim', 'default': 'feature'},
                                        {'param': 'statistic_dim', 'default': 'statistic'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.26'],
     'dependency_imports': ['numpy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Bonferroni correction：接收 1 个输入，输出 Form；主要参数：特征维度、Statistic Dim、Value Dim。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        statistic_dim = ctx.step_params.get("statistic_dim", "statistic")
        value_dim = ctx.step_params.get("value_dim", "pvalue")
        if feature_dim not in form.dims or statistic_dim not in form.dims:
            raise StepError(f"bonferroni: expected dims {feature_dim!r} and {statistic_dim!r}, got {form.dims}")
        labels = form.labels[statistic_dim]
        if value_dim not in labels:
            raise StepError(f"bonferroni: value dimension {value_dim!r} is not in {sorted(labels)}")
        axis = form.dims.index(statistic_dim)
        values = np.moveaxis(np.asarray(form.data, dtype=np.float64), axis, -1)
        pvalues = values[..., labels[value_dim]]
        if np.any(~np.isfinite(pvalues)):
            raise StepError("bonferroni: p-values must be finite")
        if np.any((pvalues < 0.0) | (pvalues > 1.0)):
            raise StepError("bonferroni: p-values must be between 0 and 1")
        m = int(pvalues.size)
        qvalues = np.minimum(pvalues * m, 1.0)
        data = qvalues.reshape(-1, 1)
        fdim = form.dims[0] if form.dims[0] != statistic_dim else form.dims[1]
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(data, dtype=np.float32),
            dims=[fdim, statistic_dim],
            labels={
                fdim: dict(form.labels[fdim]),
                statistic_dim: {"qvalue": 0},
            },
            info={"missing_code": np.nan, "correction": "bonferroni", "n_tests": m},
        )
        self._export = {"n_tests": m, "method": "bonferroni"}
        print(f"[bonferroni] {m} tests")

    def export(self, ctx: Context) -> dict:
        return self._export
