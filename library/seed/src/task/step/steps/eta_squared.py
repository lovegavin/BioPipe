"""Eta-squared effect size from one-way group means."""
from __future__ import annotations

import numpy as np

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import grouped


class EtaSquaredStep(Step):
    provider = 'operon-core'
    """Per-feature eta-squared, the between-group share of total variance."""
    parameters_file = 'eta_squared.EtaSquaredStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'eta_squared',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Eta squared',
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
     'description': 'Per-feature eta-squared, the between-group share of total variance.'}


    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        columns, features, groups = grouped(
            data, meta,
            ctx.step_params.get("sample_dim", "sample"),
            ctx.step_params.get("feature_dim", "feature"),
            ctx.step_params.get("group_dim", "sample"),
            ctx.step_params["group_label"],
        )
        rows = []
        for i in range(len(features)):
            values = [col[:, i] for col in columns]
            all_values = np.concatenate(values)
            grand = float(np.mean(all_values))
            ss_total = float(np.sum((all_values - grand) ** 2))
            ss_between = float(sum(len(v) * (np.mean(v) - grand) ** 2 for v in values))
            rows.append([ss_between / ss_total if ss_total > 0 else float("nan")])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[ctx.step_params.get("feature_dim", "feature"), "statistic"],
            labels={
                ctx.step_params.get("feature_dim", "feature"): {name: i for i, name in enumerate(features)},
                "statistic": {"eta2": 0},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {"n_features": len(features), "n_groups": len(groups)}
        print(f"[eta_squared] {len(features)} features, {len(groups)} groups")

    def export(self, ctx: Context) -> dict:
        return self._export_data
