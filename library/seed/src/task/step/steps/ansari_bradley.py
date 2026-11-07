"""Ansari-Bradley two-sample test for equality of scales."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order
from ._tests39_common import select_groups


class AnsariBradleyStep(Step):
    provider = 'operon-core'
    """Ansari-Bradley rank test for a difference in scale.

    Uses the normal approximation implemented by base R
    ``stats::ansari.test(exact = FALSE)``. The exact conditional
    distribution is not evaluated, so small samples with no ties can differ
    slightly from R's default exact branch.
    """
    parameters_file = 'ansari_bradley.AnsariBradleyStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'ansari_bradley',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Ansari-Bradley scale test',
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
     'description': 'Ansari-Bradley rank test for a difference in scale.'}


    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        alternative = ctx.step_params.get("alternative", "two-sided")
        X, codes, _, group_a, group_b = select_groups(
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
            result = _ansari_bradley(x, y, alternative)
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
                    "AB": 0,
                    "z": 1,
                    "p": 2,
                    "n_a": 3,
                    "n_b": 4,
                    "ties": 5,
                },
            },
            info={
                "missing_code": np.nan,
                "test": "Ansari-Bradley",
                "method": "normal approximation",
                "alternative": alternative,
                "group_a": group_a,
                "group_b": group_b,
                "n_features": len(kept),
            },
        )
        self._export_data = {
            "n_features": len(kept),
            "test": "Ansari-Bradley",
            "alternative": alternative,
            "method": "normal approximation",
        }
        print(f"[{self.name}] {len(kept)} features, {x.size} vs {y.size}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _ansari_bradley(x: np.ndarray, y: np.ndarray, alternative: str):
    m = int(x.size)
    n = int(y.size)
    N = m + n
    combined = np.concatenate([x, y])
    ranks = stats.rankdata(combined)
    scores = np.minimum(ranks, N - ranks + 1.0)
    statistic = float(np.sum(scores[:m]))
    ties = bool(np.unique(combined).size != combined.size)
    even = N % 2 == 0
    if even:
        center = m * (N + 2.0) / 4.0
    else:
        center = m * (N + 1.0) ** 2 / (4.0 * N)
    if not ties:
        if even:
            variance = m * n * (N + 2.0) * (N - 2.0) / (48.0 * (N - 1.0))
        else:
            variance = m * n * (N + 1.0) * (3.0 + N * N) / (48.0 * N * N)
    else:
        values, counts = np.unique(scores, return_counts=True)
        weighted = float(np.sum(counts * values**2))
        if even:
            variance = (
                m
                * n
                * (16.0 * weighted - N * (N + 2.0) ** 2)
                / (16.0 * N * (N - 1.0))
            )
        else:
            variance = (
                m
                * n
                * (16.0 * N * weighted - (N + 1.0) ** 4)
                / (16.0 * N * N * (N - 1.0))
            )
    if variance <= 0 or not np.isfinite(variance):
        return None
    z_value = float((statistic - center) / np.sqrt(variance))
    upper = float(stats.norm.cdf(z_value))
    if alternative == "less":
        p_value = 1.0 - upper
    elif alternative == "greater":
        p_value = upper
    else:
        p_value = 2.0 * min(upper, 1.0 - upper)
    p_value = float(min(1.0, max(0.0, p_value)))
    return [statistic, z_value, p_value, float(m), float(n), float(ties)]
