"""Mood two-sample test of scale."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._tests39_common import select_groups
from ._ext_common import labels_in_order


class MoodScaleStep(Step):
    provider = 'operon-core'
    """Mood's two-sample rank test for equality of scale."""
    parameters_file = 'mood_scale.MoodScaleStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'mood_scale',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Mood two-sample scale test',
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
     'description': "Mood's two-sample rank test for equality of scale."}


    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        alternative = ctx.step_params.get("alternative", "two-sided")
        X, codes, _, _, _ = select_groups(
            data,
            meta,
            sample_dim,
            feature_dim,
            group_dim,
            ctx.step_params["group_label"],
            ctx.step_params["group_a"],
            ctx.step_params["group_b"],
            self.name,
        )
        features = labels_in_order(data, feature_dim)
        rows = []
        kept = []
        for j, feature in enumerate(features):
            x = X[codes == 0, j]
            y = X[codes == 1, j]
            x = x[np.isfinite(x)]
            y = y[np.isfinite(y)]
            if x.size < 2 or y.size < 2:
                continue
            result = _mood(x, y, alternative)
            if result is None:
                continue
            rows.append(result)
            kept.append(feature)

        if not rows:
            raise StepError(f"{self.name}: no feature had two finite values in each group")
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["feature", "statistic"],
            labels={
                "feature": {name: i for i, name in enumerate(kept)},
                "statistic": {
                    "z": 0,
                    "p": 1,
                    "n_a": 2,
                    "n_b": 3,
                    "ties": 4,
                },
            },
            info={
                "missing_code": np.nan,
                "test": "Mood scale",
                "alternative": alternative,
                "n_features": len(kept),
            },
        )
        self._export_data = {
            "n_features": len(kept),
            "test": "Mood scale",
            "alternative": alternative,
        }
        print(f"[{self.name}] {len(kept)} features, {len(x)} vs {len(y)}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})



def _mood(x: np.ndarray, y: np.ndarray, alternative: str):
    m = x.size
    n = y.size
    N = m + n
    expected = m * (N * N - 1) / 12.0
    variance = m * n * (N + 1) * (N + 2) * (N - 2) / 180.0
    combined = np.concatenate([x, y])
    if np.unique(combined).size == combined.size:
        ranks = stats.rankdata(combined)
        ties = 0.0
        statistic = float(np.sum((ranks[:m] - (N + 1) / 2.0) ** 2))
    else:
        ties = 1.0
        values, counts = np.unique(combined, return_counts=True)
        x_counts = np.array([np.sum(x == value) for value in values], dtype=float)
        tail = np.cumsum((np.arange(1, N + 1) - (N + 1) / 2.0) ** 2)
        positions = np.cumsum(counts) - 1
        increments = np.diff(np.r_[0.0, tail[positions]])
        statistic = float(np.sum(x_counts * increments / counts))
        variance -= m * n / (180.0 * N * (N - 1.0)) * np.sum(
            counts * (counts ** 2 - 1.0) * (counts ** 2 - 4.0 + 15.0 * (N - counts) ** 2)
        )
    if variance <= 0:
        return None
    z = (statistic - expected) / np.sqrt(variance)
    if alternative == "less":
        p_value = float(stats.norm.cdf(z))
    elif alternative == "greater":
        p_value = float(stats.norm.sf(z))
    else:
        p_value = float(min(1.0, 2.0 * min(stats.norm.cdf(z), stats.norm.sf(z))))
    return [float(z), p_value, float(m), float(n), ties]
