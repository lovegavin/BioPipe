"""Tukey HSD post-hoc pairwise comparisons."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import grouped


class TukeyHsdStep(Step):
    provider = 'operon-core'
    """Tukey HSD across groups for every feature."""
    parameters_file = 'tukey_hsd.TukeyHsdStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'tukey_hsd',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Tukey HSD',
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
     'dependencies': ['statsmodels>=0.14'],
     'dependency_imports': ['statsmodels'],
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Tukey HSD across groups for every feature.'}


    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.stats.multicomp import pairwise_tukeyhsd

        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        columns, features, groups = grouped(
            data, meta, sample_dim, feature_dim, group_dim, ctx.step_params["group_label"]
        )
        if len(groups) < 2:
            raise StepError("tukey_hsd needs at least two groups")
        alpha = float(ctx.step_params.get("alpha", 0.05))
        rows = []
        comparisons = []
        for i, feature in enumerate(features):
            values = [col[:, i] for col in columns]
            all_values = np.concatenate(values)
            all_groups = np.concatenate([
                np.full(len(v), g, dtype=object) for g, v in zip(groups, values)
            ])
            result = pairwise_tukeyhsd(all_values, all_groups, alpha=alpha)
            table = result.summary()
            for row in table.data[1:]:
                comparisons.append(f"{feature}: {row[0]} vs {row[1]}")
                rows.append([
                    float(row[2]), float(row[3]), float(row[4]),
                    float(row[5]), 1.0 if bool(row[6]) else 0.0,
                ])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["comparison", "statistic"],
            labels={
                "comparison": {name: i for i, name in enumerate(comparisons)},
                "statistic": {"diff": 0, "P": 1, "CI_low": 2, "CI_high": 3, "reject": 4},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {
            "n_features": len(features),
            "n_groups": len(groups),
            "n_comparisons": len(comparisons),
            "alpha": alpha,
        }
        print(f"[tukey_hsd] {len(features)} features, {len(comparisons)} comparisons")

    def export(self, ctx: Context) -> dict:
        return self._export_data
