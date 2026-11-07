"""Cliff's delta effect size for exactly two groups."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import grouped


class CliffsDeltaStep(Step):
    provider = 'operon-core'
    """Per-feature Cliff's delta, positive when group0 tends larger."""
    parameters_file = 'cliffs_delta.CliffsDeltaStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'cliffs_delta',
     'version': '1.0.0',
     'kind': 'operator',
     'title': "Cliff's delta",
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
     'dependencies': ['numpy>=1.26'],
     'dependency_imports': ['numpy'],
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': "Per-feature Cliff's delta, positive when group0 tends larger."}


    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        columns, features, groups = grouped(
            data, meta,
            ctx.step_params.get("sample_dim", "sample"),
            ctx.step_params.get("feature_dim", "feature"),
            ctx.step_params.get("group_dim", "sample"),
            ctx.step_params["group_label"],
        )
        if len(groups) != 2:
            raise StepError("cliffs_delta needs exactly two groups")
        rows = []
        for i in range(len(features)):
            a, b = columns[0][:, i], columns[1][:, i]
            delta = float((np.sum(a[:, None] > b[None, :]) - np.sum(a[:, None] < b[None, :])) / (len(a) * len(b)))
            rows.append([delta])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[ctx.step_params.get("feature_dim", "feature"), "statistic"],
            labels={
                ctx.step_params.get("feature_dim", "feature"): {name: i for i, name in enumerate(features)},
                "statistic": {"delta": 0},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {"n_features": len(features), "n_groups": 2}
        print(f"[cliffs_delta] {len(features)} features")

    def export(self, ctx: Context) -> dict:
        return self._export_data
