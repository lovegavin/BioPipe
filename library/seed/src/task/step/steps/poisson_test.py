"""Exact Poisson rate test and confidence interval for a single sample."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame


def _two_sided(counts, expected):
    """Exact two-sided p-value using R's equal-density rule (stats::poisson.test)."""
    p = np.empty(counts.shape, dtype=np.float64)
    rel = 1.0 + 1e-7
    for i, (x, m) in enumerate(zip(counts, expected)):
        if m == 0.0:
            p[i] = 1.0 if x == 0 else 0.0
            continue
        if x == m:
            p[i] = 1.0
            continue
        d = stats.poisson.pmf(x, m)
        if x < m:
            n = int(np.ceil(2.0 * m - x))
            while stats.poisson.pmf(n, m) > d:
                n *= 2
            idx = np.arange(int(np.ceil(m)), n + 1)
            y = int(np.sum(stats.poisson.pmf(idx, m) <= d * rel))
            p[i] = stats.poisson.cdf(x, m) + stats.poisson.sf(n - y, m)
        else:
            idx = np.arange(0, int(np.floor(m)) + 1)
            y = int(np.sum(stats.poisson.pmf(idx, m) <= d * rel))
            p[i] = stats.poisson.cdf(y - 1, m) + stats.poisson.sf(x - 1, m)
    return np.clip(p, 0.0, 1.0)

class PoissonTestStep(Step):
    provider = 'operon-core'
    parameters_file = 'poisson_test.PoissonTestStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'poisson_test',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Exact Poisson rate test',
        'category': 'Statistics',
        'contracts': {
            'version': 1,
            'inputs': [{
                'version': 1,
                'numeric': True,
                'info': {},
                'dims': [{'param': 'sample_dim', 'default': 'sample'},
                         {'param': 'feature_dim', 'default': 'feature'}],
                'labels': [],
                'parallel': [],
                'ndim': 2,
            }],
            'output': {'mode': 'declare',
                       'schema': {'ndim': 2, 'numeric': True,
                                  'info_open': True, 'axis_info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'dependencies': ['scipy>=1.11'],
        'dependency_imports': ['scipy'],
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
        'description': 'Exact conditional Poisson test of an observed count against '
                       'a null rate, with a gamma confidence interval.',
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        counts_label = ctx.step_params["counts_label"]
        exposure_label = ctx.step_params["exposure_label"]
        null_rate = float(ctx.step_params.get("rate", 1.0))
        alternative = ctx.step_params.get("alternative", "two-sided")
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)
        if alternative not in ("two-sided", "greater", "less"):
            raise StepError("poisson_test: alternative must be two-sided, greater or less")
        if not 0.0 < confidence < 1.0:
            raise StepError("poisson_test: confidence must be strictly between 0 and 1")
        if not np.isfinite(null_rate) or null_rate <= 0.0:
            raise StepError("poisson_test: rate must be a positive finite number")

        frame = table_frame(form, sample_dim, feature_dim, "poisson_test")
        names = frame["__sample__"].astype(str).to_numpy()
        counts = np.asarray(numeric_column(frame, counts_label, "poisson_test"),
                            dtype=np.float64)
        exposure = np.asarray(numeric_column(frame, exposure_label, "poisson_test"),
                              dtype=np.float64)
        mask = np.isfinite(counts) & np.isfinite(exposure)
        counts, exposure, names = counts[mask], exposure[mask], names[mask]
        if counts.size == 0:
            raise StepError("poisson_test: no finite observations")
        if np.any(exposure <= 0.0):
            raise StepError("poisson_test: exposure must be positive")
        if np.any(counts < 0.0) or np.any(counts != np.round(counts)):
            raise StepError("poisson_test: counts must be non-negative integers")

        alpha = 1.0 - confidence
        expected = null_rate * exposure
        lower_p = stats.poisson.cdf(counts, expected)
        upper_p = stats.poisson.sf(counts - 1.0, expected)
        if alternative == "greater":
            p_value = upper_p
        elif alternative == "less":
            p_value = lower_p
        else:
            p_value = _two_sided(counts, expected)
        ci_low = np.where(counts > 0, stats.gamma.ppf(alpha / 2.0, counts), 0.0) / exposure
        ci_high = stats.gamma.ppf(1.0 - alpha / 2.0, counts + 1.0) / exposure

        stats_names = ("rate", "ci_low", "ci_high", "p_value", "expected")
        data = np.column_stack(
            [counts / exposure, ci_low, ci_high, p_value, expected])
        observations = {f"{i}:{name}": i for i, name in enumerate(names)}

        out = Form(
            data=data.astype(np.float32),
            dims=["observation", "statistic"],
            labels={"observation": observations,
                    "statistic": {name: j for j, name in enumerate(stats_names)}},
            info={"missing_code": np.nan, "method": "exact Poisson",
                  "alternative": alternative, "null_rate": null_rate,
                  "confidence": confidence, "n_observations": int(counts.size)},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "rate": (counts / exposure).tolist(), "p_value": p_value.tolist(),
            "ci_low": ci_low.tolist(), "ci_high": ci_high.tolist(),
            "null_rate": null_rate, "alternative": alternative,
        }
        print(f"[poisson_test] {counts.size} observations, rate={null_rate:g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
