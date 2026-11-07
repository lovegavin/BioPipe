"""Nemenyi all-pairwise post-hoc test after Kruskal-Wallis."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._matrix_common import grouped


class NemenyiTestStep(Step):
    provider = 'operon-core'
    """All-pairwise Nemenyi comparisons using mean ranks.

    The two-sided p-values use the studentized range distribution with
    infinite degrees of freedom, matching
    ``DescTools::NemenyiTest(x, g, dist = "tukey")``.
    """
    parameters_file = 'nemenyi_test.NemenyiTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'nemenyi_test',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Nemenyi post-hoc test',
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
     'description': 'All-pairwise Nemenyi comparisons using mean ranks.'}


    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        columns, features, groups = grouped(
            data, meta, sample_dim, feature_dim, group_dim, ctx.step_params["group_label"]
        )
        if len(groups) < 2:
            raise StepError("nemenyi_test needs at least two groups")
        rows = []
        comparisons = []
        for i, feature in enumerate(features):
            values = []
            for col in columns:
                value = np.asarray(col[:, i], dtype=np.float64)
                value = value[np.isfinite(value)]
                if value.size == 0:
                    values = []
                    break
                values.append(value)
            if len(values) < 2:
                continue
            sizes = [int(value.size) for value in values]
            n_total = sum(sizes)
            if n_total < len(values) + 1:
                continue
            ranks = stats.rankdata(np.concatenate(values), method="average")
            starts = np.cumsum([0] + sizes[:-1])
            mean_ranks = [float(ranks[start:start + size].mean()) for start, size in zip(starts, sizes)]
            offset = n_total * (n_total + 1) / 12.0
            k = len(values)
            for a in range(k - 1):
                for b in range(a + 1, k):
                    diff = mean_ranks[a] - mean_ranks[b]
                    variance = offset * (1.0 / sizes[a] + 1.0 / sizes[b])
                    if variance <= 0.0:
                        continue
                    z_value = float(diff / np.sqrt(variance))
                    p_value = float(
                        stats.studentized_range.sf(abs(z_value) * np.sqrt(2.0), k, np.inf)
                    )
                    key = f"{feature}: {groups[a]} vs {groups[b]}"
                    comparisons.append(key)
                    rows.append([
                        diff,
                        p_value,
                        z_value,
                        mean_ranks[a],
                        mean_ranks[b],
                        float(sizes[a]),
                        float(sizes[b]),
                    ])

        if not rows:
            raise StepError("nemenyi_test: no feature had enough finite group data")
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["comparison", "statistic"],
            labels={
                "comparison": {name: i for i, name in enumerate(comparisons)},
                "statistic": {
                    "rank_diff": 0,
                    "p": 1,
                    "z": 2,
                    "mean_rank_a": 3,
                    "mean_rank_b": 4,
                    "n_a": 5,
                    "n_b": 6,
                },
            },
            info={"missing_code": np.nan, "method": "Nemenyi", "distribution": "tukey"},
        )
        self._export_data = {
            "n_features": len(features),
            "n_groups": len(groups),
            "n_comparisons": len(comparisons),
        }
        print(f"[nemenyi_test] {len(features)} features, {len(comparisons)} comparisons")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
