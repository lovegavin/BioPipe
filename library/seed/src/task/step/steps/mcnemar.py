"""McNemar test for paired binary labels."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form


class McnemarStep(Step):
    provider = 'operon-core'
    parameters_file = 'mcnemar.McnemarStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'mcnemar',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'McNemar test',
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
     'description': 'McNemar test：接收 1 个输入，输出 Form；主要参数：样本维度、特征维度、Label A、Label B、Exact。'}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        a_name = ctx.step_params["label_a"]; b_name = ctx.step_params["label_b"]
        exact = bool(ctx.step_params.get("exact", True))
        out_name = ctx.step_params.get("output", self.name)
        for name in (a_name, b_name):
            if name not in form.labels.get(feature_dim, {}):
                raise StepError(f"mcnemar: column {name!r} not found")
        data = np.moveaxis(np.asarray(form.data), form.dims.index(sample_dim), 0)
        a = data[:, form.labels[feature_dim][a_name]]
        b = data[:, form.labels[feature_dim][b_name]]
        keep = np.isfinite(a) & np.isfinite(b)
        a, b = (a[keep] > 0), (b[keep] > 0)
        b01 = int(np.sum((~a) & b))
        b10 = int(np.sum(a & (~b)))
        n = b01 + b10
        if n == 0:
            stat, p = 0.0, 1.0
        elif exact:
            stat = float(min(b01, b10))
            p = float(stats.binomtest(min(b01, b10), n, 0.5).pvalue)
        else:
            stat = float((abs(b01 - b10) - 1.0) ** 2 / n)
            p = float(stats.chi2.sf(stat, 1))
        out = make_form([[b01], [b10], [stat], [p]], ["statistic", "value"],
                        {"statistic": {"b01": 0, "b10": 1, "statistic": 2, "p": 3}, "value": {"value": 0}})
        ctx[out_name] = out
        self._export_data = {"b01": b01, "b10": b10, "statistic": stat, "p": p, "exact": exact}

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
