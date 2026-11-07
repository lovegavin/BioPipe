"""Scheffe post-hoc pairwise comparisons after one-way ANOVA."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._matrix_common import grouped


class ScheffeTestStep(Step):
    provider = 'operon-core'
    """All-pairwise Scheffe comparisons for every feature.

    The family-wise confidence intervals and p-values use the ANOVA residual
    mean square and the F distribution; this matches
    ``DescTools::ScheffeTest(aov(x ~ g))``.
    """
    parameters_file = 'scheffe_test.ScheffeTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'scheffe_test',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Scheffe post-hoc test',
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
     'description': 'All-pairwise Scheffe comparisons for every feature.'}


    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        columns, features, groups = grouped(
            data, meta, sample_dim, feature_dim, group_dim, ctx.step_params["group_label"]
        )
        if len(groups) < 2:
            raise StepError("scheffe_test needs at least two groups")
        alpha = float(ctx.step_params.get("alpha", 0.05))
        rows = []
        comparisons = []
        for i, feature in enumerate(features):
            values = []
            means = []
            sizes = []
            for col in columns:
                value = np.asarray(col[:, i], dtype=np.float64)
                value = value[np.isfinite(value)]
                if value.size == 0:
                    values = []
                    break
                values.append(value)
                means.append(float(value.mean()))
                sizes.append(int(value.size))
            if len(values) < 2:
                continue
            n_total = sum(sizes)
            k = len(values)
            df1 = k - 1
            df2 = n_total - k
            if df2 <= 0:
                continue
            sse = float(sum(np.sum((value - mean) ** 2) for value, mean in zip(values, means)))
            mse = sse / df2
            for a in range(k - 1):
                for b in range(a + 1, k):
                    diff = means[a] - means[b]
                    ss = 1.0 / sizes[a] + 1.0 / sizes[b]
                    if mse <= 0.0:
                        p_value = 1.0 if diff == 0.0 else 0.0
                        half = 0.0
                    else:
                        f_value = diff * diff / (mse * ss * df1)
                        p_value = float(stats.f.sf(f_value, df1, df2))
                        critical = df1 * float(stats.f.ppf(1.0 - alpha, df1, df2))
                        half = float(np.sqrt(max(0.0, critical * mse * ss)))
                    key = f"{feature}: {groups[a]} vs {groups[b]}"
                    comparisons.append(key)
                    rows.append([
                        diff,
                        p_value,
                        diff - half,
                        diff + half,
                        means[a],
                        means[b],
                        float(sizes[a]),
                        float(sizes[b]),
                    ])

        if not rows:
            raise StepError("scheffe_test: no feature had enough finite group data")
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["comparison", "statistic"],
            labels={
                "comparison": {name: i for i, name in enumerate(comparisons)},
                "statistic": {
                    "diff": 0,
                    "p": 1,
                    "ci_low": 2,
                    "ci_high": 3,
                    "mean_a": 4,
                    "mean_b": 5,
                    "n_a": 6,
                    "n_b": 7,
                },
            },
            info={"missing_code": np.nan, "alpha": alpha, "method": "Scheffe"},
        )
        self._export_data = {
            "n_features": len(features),
            "n_groups": len(groups),
            "n_comparisons": len(comparisons),
            "alpha": alpha,
        }
        print(f"[scheffe_test] {len(features)} features, {len(comparisons)} comparisons")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
