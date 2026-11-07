"""Confidence intervals for binomial proportions (exact and approximate)."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame

METHODS = ("wilson", "clopper_pearson", "agresti_coull", "jeffreys", "wald")


class ProportionCiStep(Step):
    provider = 'operon-core'
    parameters_file = 'proportion_ci.ProportionCiStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'proportion_ci',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Binomial proportion confidence interval',
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
        'description': 'Confidence intervals for binomial proportions using '
                       'Wilson, Clopper-Pearson, Agresti-Coull, Jeffreys or Wald.',
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        successes_label = ctx.step_params["successes_label"]
        trials_label = ctx.step_params["trials_label"]
        method = ctx.step_params.get("method", "wilson")
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)
        if method not in METHODS:
            raise StepError(f"proportion_ci: unknown method {method!r}")
        if not 0.0 < confidence < 1.0:
            raise StepError("proportion_ci: confidence must be strictly between 0 and 1")

        frame = table_frame(form, sample_dim, feature_dim, "proportion_ci")
        names = frame["__sample__"].astype(str).to_numpy()
        x = np.asarray(numeric_column(frame, successes_label, "proportion_ci"),
                       dtype=np.float64)
        n = np.asarray(numeric_column(frame, trials_label, "proportion_ci"),
                       dtype=np.float64)
        mask = np.isfinite(x) & np.isfinite(n)
        x, n, names = x[mask], n[mask], names[mask]
        if x.size == 0:
            raise StepError("proportion_ci: no finite observations")
        if np.any(n <= 0):
            raise StepError("proportion_ci: every trial count must be positive")
        if np.any((x < 0) | (x > n)):
            raise StepError("proportion_ci: successes must lie between 0 and trials")
        if np.any(x != np.round(x)) or np.any(n != np.round(n)):
            raise StepError("proportion_ci: successes and trials must be integers")

        p = x / n
        alpha = 1.0 - confidence
        z = stats.norm.ppf(1.0 - alpha / 2.0)
        if method == "wilson":
            denom = 1.0 + z * z / n
            centre = (p + z * z / (2.0 * n)) / denom
            half = z * np.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
            low, high = centre - half, centre + half
        elif method == "clopper_pearson":
            low = np.where(x > 0, stats.beta.ppf(alpha / 2.0, x, n - x + 1.0), 0.0)
            high = np.where(x < n, stats.beta.ppf(1.0 - alpha / 2.0, x + 1.0, n - x), 1.0)
        elif method == "agresti_coull":
            nt = n + z * z
            pt = (x + z * z / 2.0) / nt
            half = z * np.sqrt(pt * (1.0 - pt) / nt)
            low, high = pt - half, pt + half
        elif method == "jeffreys":
            low = stats.beta.ppf(alpha / 2.0, x + 0.5, n - x + 0.5)
            high = stats.beta.ppf(1.0 - alpha / 2.0, x + 0.5, n - x + 0.5)
        else:  # wald
            half = z * np.sqrt(p * (1.0 - p) / n)
            low, high = p - half, p + half
        low = np.clip(low, 0.0, 1.0)
        high = np.clip(high, 0.0, 1.0)

        stats_names = ("p_hat", "ci_low", "ci_high")
        data = np.column_stack([p, low, high])
        observations = {f"{i}:{name}": i for i, name in enumerate(names)}

        out = Form(
            data=data.astype(np.float32),
            dims=["observation", "statistic"],
            labels={"observation": observations,
                    "statistic": {name: j for j, name in enumerate(stats_names)}},
            info={"missing_code": np.nan, "method": method,
                  "confidence": confidence, "n_observations": int(x.size)},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "method": method, "confidence": confidence,
            "p_hat": p.tolist(), "ci_low": low.tolist(), "ci_high": high.tolist(),
        }
        print(f"[proportion_ci] {method}: {x.size} observations")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


from src.core import Form  # noqa: E402
