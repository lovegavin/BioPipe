"""Mood two-sample test of scale."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import grouped


class MoodMedianStep(Step):
    provider = 'operon-core'
    parameters_file = 'mood_median.MoodMedianStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'mood_median',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Mood two-sample scale test',
        'category': 'Statistics',
        'contracts': {
            'version': 1,
            'inputs': [
                {'version': 1, 'numeric': True, 'info': {},
                 'dims': [{'param': 'feature_dim', 'default': 'feature'},
                          {'param': 'sample_dim', 'default': 'sample'}],
                 'labels': [], 'parallel': [], 'ndim': 2},
                {'version': 1, 'numeric': True, 'info': {},
                 'dims': [{'param': 'sample_dim', 'default': 'sample'},
                          {'param': 'group_dim', 'default': 'feature'}],
                 'labels': [], 'parallel': [], 'ndim': 2},
            ],
            'output': {'mode': 'declare',
                       'schema': {'ndim': 2, 'numeric': True,
                                  'info_open': True, 'axis_info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'dependencies': ['numpy>=1.24', 'scipy>=1.11'],
        'dependency_imports': ['numpy', 'scipy'],
        'inputs_arity': 2,
        'outputs': [],
        'output_parameter': 'output',
        'description': 'Mood two-sample test of scale: compares the dispersion of '
                       'two groups from the ranked pooled sample.',
    }

    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        alternative = ctx.step_params.get("alternative", "two-sided")
        columns, features, groups = grouped(
            data, meta, sample_dim, feature_dim, group_dim,
            ctx.step_params["group_label"],
        )
        if len(columns) != 2:
            raise StepError(f"mood_median needs exactly two groups, got {len(groups)}")
        rows = []
        for i in range(len(features)):
            x = np.asarray(columns[0][:, i], dtype=np.float64)
            y = np.asarray(columns[1][:, i], dtype=np.float64)
            x = x[np.isfinite(x)]
            y = y[np.isfinite(y)]
            rows.append(self._test(x, y, alternative))
        block = np.asarray(rows, dtype=np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=block,
            dims=[feature_dim, "statistic"],
            labels={feature_dim: {name: i for i, name in enumerate(features)},
                    "statistic": {"Z": 0, "p_value": 1, "n_x": 2, "n_y": 3}},
            info={"missing_code": np.nan, "method": "mood_median"},
        )
        self._export = {
            "method": "mood_median",
            "groups": groups,
            "features": features,
            "n_features": len(features),
        }
        print(f"[mood_median] {len(features)} features, groups={groups}")

    @staticmethod
    def _test(x: np.ndarray, y: np.ndarray, alternative: str) -> list[float]:
        m = x.size
        n = y.size
        total = m + n
        if total < 3:
            raise StepError("mood_median: need at least three observations")
        expected = m * (total * total - 1.0) / 12.0
        variance = m * n * (total + 1.0) * (total + 2.0) * (total - 2.0) / 180.0
        pooled = np.concatenate([x, y])
        uniq = np.unique(pooled)
        if uniq.size == total:
            ranks = stats.rankdata(pooled)
            statistic = float(np.sum((ranks[:m] - (total + 1.0) / 2.0) ** 2))
        else:
            counts_x = np.array([np.sum(x == value) for value in uniq], dtype=np.float64)
            counts_all = np.array([np.sum(pooled == value) for value in uniq], dtype=np.float64)
            positions = np.arange(1, total + 1, dtype=np.float64)
            cumulative = np.cumsum((positions - (total + 1.0) / 2.0) ** 2)
            ends = np.cumsum(counts_all).astype(int)
            block = np.diff(np.concatenate(([0.0], cumulative[ends - 1])))
            variance -= (m * n) / (180.0 * total * (total - 1.0)) * float(
                np.sum(counts_all * (counts_all ** 2 - 1.0)
                       * (counts_all ** 2 - 4.0 + 15.0 * (total - counts_all) ** 2))
            )
            statistic = float(np.sum(counts_x * block / counts_all))
        if not variance > 0.0:
            raise StepError("mood_median: variance is not positive")
        z = (statistic - expected) / np.sqrt(variance)
        upper = float(stats.norm.sf(z))
        if alternative == "less":
            p_value = float(stats.norm.cdf(z))
        elif alternative == "greater":
            p_value = upper
        else:
            p_value = min(1.0, 2.0 * min(float(stats.norm.cdf(z)), upper))
        return [float(z), float(p_value), float(m), float(n)]

    def export(self, ctx: Context) -> dict:
        return self._export
