"""Yuen's two-sample trimmed-mean test."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, make_form
from ._tests39_common import select_groups, yuen_columns


class YuenTestStep(Step):
    provider = 'operon-core'
    parameters_file = 'yuen_test.YuenTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'yuen_test',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Yuen trimmed-mean test',
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
     'dependencies': [],
     'dependency_imports': [],
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Yuen trimmed-mean test：接收 2 个输入，输出 Form；主要参数：特征维度、样本维度、分组维度、分组字段、A 组、B 组。'}

    def run(self, ctx: Context, inputs) -> None:
        expr, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        trim = float(ctx.step_params.get("trim", 0.2))
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)
        data, codes, _samples, group_a, group_b = select_groups(
            expr, meta, sample_dim, feature_dim, group_dim,
            ctx.step_params["group_label"], ctx.step_params["group_a"], ctx.step_params["group_b"],
            "yuen_test",
        )
        features = labels_in_order(expr, feature_dim)
        columns = ["diff", "t", "df", "p", "ci_low", "ci_high", "mean_a", "mean_b", "n_a", "n_b"]
        rows = []
        for j in range(data.shape[1]):
            values = yuen_columns(data[codes == 0, j], data[codes == 1, j], trim, confidence)
            if values is None:
                rows.append([np.nan] * len(columns))
            else:
                rows.append(values)
        if not any(np.isfinite(row[0]) for row in rows):
            raise StepError("yuen_test: no feature has enough finite observations")
        out = make_form(
            np.asarray(rows, dtype=np.float64),
            [feature_dim, "statistic"],
            {feature_dim: {name: i for i, name in enumerate(features)},
             "statistic": {name: i for i, name in enumerate(columns)}},
        )
        out.info.update({"group_a": group_a, "group_b": group_b, "trim": trim, "confidence": confidence})
        ctx[out_name] = out
        self._export_data = {
            "group_a": group_a, "group_b": group_b, "trim": trim,
            "confidence": confidence, "n_features": len(features),
        }
        print(f"[yuen_test] features={len(features)} trim={trim:g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
