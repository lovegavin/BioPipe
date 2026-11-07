"""Fligner-Killeen test for homogeneity of variances across groups."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._tests50_common import grouped_expression


class FlignerKilleenStep(Step):
    provider = 'operon-core'
    """Fligner-Killeen median-centered rank test for each feature."""
    parameters_file = 'fligner_killeen.FlignerKilleenStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'fligner_killeen',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Fligner-Killeen variance homogeneity test',
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
                               'dims': [{'param': 'group_dim', 'default': 'sample'},
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
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Fligner-Killeen median-centered rank test for each feature.'}


    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        X, features, _, groups, labels = grouped_expression(
            data, meta, sample_dim, feature_dim, group_dim, ctx.step_params["group_label"]
        )
        group_array = np.asarray(groups)
        rows = []
        kept = []
        for j, feature in enumerate(features):
            values = []
            for label in labels:
                column = X[group_array == label, j]
                column = column[np.isfinite(column)]
                if column.size < 2:
                    values = []
                    break
                values.append(column)
            if not values:
                continue
            centered = np.concatenate([value - np.median(value) for value in values])
            n = centered.size
            if n < 3:
                continue
            scores = stats.norm.ppf((1.0 + stats.rankdata(np.abs(centered)) / (n + 1.0)) / 2.0)
            scores = scores - scores.mean()
            variance = float(np.sum(scores * scores) / (n - 1))
            if variance <= 0:
                continue
            statistic = float(sum(value.size * np.mean(scores[offset:offset + value.size]) ** 2
                                  for value, offset in _offsets(values)) / variance)
            df = len(values) - 1
            p_value = float(stats.chi2.sf(statistic, df))
            rows.append([statistic, p_value, float(df), float(len(values)), float(n)])
            kept.append(feature)

        if not rows:
            raise StepError(f"{self.name}: no feature had two finite values in every group")
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["feature", "statistic"],
            labels={
                "feature": {name: i for i, name in enumerate(kept)},
                "statistic": {
                    "statistic": 0,
                    "p": 1,
                    "df": 2,
                    "n_groups": 3,
                    "n": 4,
                },
            },
            info={
                "missing_code": np.nan,
                "test": "Fligner-Killeen",
                "center": "median",
                "n_features": len(kept),
                "n_groups": len(labels),
            },
        )
        self._export_data = {
            "n_features": len(kept),
            "n_groups": len(labels),
            "test": "Fligner-Killeen",
        }
        print(f"[{self.name}] {len(kept)} features, {len(labels)} groups")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _offsets(values):
    start = 0
    for value in values:
        yield value, start
        start += value.size
