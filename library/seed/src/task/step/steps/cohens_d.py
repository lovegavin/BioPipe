"""Cohen's d and Hedges' g for exactly two groups."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import grouped


class CohensDStep(Step):
    provider = 'operon-core'
    """Per-feature standardized mean difference between two groups."""
    parameters_file = 'cohens_d.CohensDStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'cohens_d',
     'version': '1.0.0',
     'kind': 'operator',
     'title': "Cohen's d",
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
     'description': 'Per-feature standardized mean difference between two groups.'}


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
            raise StepError("cohens_d needs exactly two groups")
        rows = []
        for i in range(len(features)):
            a, b = columns[0][:, i], columns[1][:, i]
            n1, n2 = len(a), len(b)
            var = ((n1 - 1) * np.var(a, ddof=1) + (n2 - 1) * np.var(b, ddof=1)) / (n1 + n2 - 2)
            if var <= 0:
                d = 0.0 if abs(np.mean(a) - np.mean(b)) < 1e-15 else float("nan")
            else:
                d = float((np.mean(a) - np.mean(b)) / np.sqrt(var))
            g = float(d * (1.0 - 3.0 / (4.0 * (n1 + n2) - 9.0))) if np.isfinite(d) else float("nan")
            rows.append([d, g])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=[ctx.step_params.get("feature_dim", "feature"), "statistic"],
            labels={
                ctx.step_params.get("feature_dim", "feature"): {name: i for i, name in enumerate(features)},
                "statistic": {"d": 0, "hedges_g": 1},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {"n_features": len(features), "n_groups": 2, "group0": int(groups[0]), "group1": int(groups[1])}
        print(f"[cohens_d] {len(features)} features, 2 groups")

    def export(self, ctx: Context) -> dict:
        return self._export_data
