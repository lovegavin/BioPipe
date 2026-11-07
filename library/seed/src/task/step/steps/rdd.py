"""Sharp regression-discontinuity estimate with a local linear fit.

Fits a weighted local linear regression on each side of a cutoff and
reports the jump at the cutoff. The default triangular kernel, fixed
bandwidth and HC0 sandwich reproduce the conventional estimate and
standard error of ``rdrobust`` with ``h = b``, ``p = 1`` and
``vce = "hc0"``.
"""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form, normal_p
from ._stats21_common import numeric_column, table_frame


def _kernel_weights(u: np.ndarray, kernel: str) -> np.ndarray:
    if kernel == "triangular":
        return np.clip(1.0 - np.abs(u), 0.0, 1.0)
    if kernel == "uniform":
        return np.ones_like(u)
    if kernel == "epanechnikov":
        return np.clip(0.75 * (1.0 - u * u), 0.0, None)
    raise StepError(f"rdd: unknown kernel {kernel!r}")


class RddStep(Step):
    provider = 'operon-core'
    parameters_file = 'rdd.RddStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'rdd',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Regression discontinuity',
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
        'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
        'dependencies': [],
        'dependency_imports': [],
        'inputs_arity': 1,
        'outputs': [],
        'output_parameter': 'output',
        'description': 'Sharp regression-discontinuity jump estimated by local linear regression near a cutoff.',
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        running_label = ctx.step_params["running_label"]
        outcome_label = ctx.step_params["outcome_label"]
        cutoff = float(ctx.step_params.get("cutoff", 0.0))
        bandwidth = float(ctx.step_params["bandwidth"])
        kernel = ctx.step_params.get("kernel", "triangular")
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)

        if not bandwidth > 0.0:
            raise StepError("rdd: bandwidth must be positive")
        if not 0.5 < confidence < 1.0:
            raise StepError("rdd: confidence must be in (0.5, 1)")

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        running = numeric_column(frame, running_label, self.name)
        outcome = numeric_column(frame, outcome_label, self.name)
        valid = np.isfinite(running) & np.isfinite(outcome)
        running = running[valid]
        outcome = outcome[valid]
        distance = running - cutoff
        inside = np.abs(distance) <= bandwidth
        if int(inside.sum()) < 8:
            raise StepError("rdd: too few observations within the bandwidth")
        distance = distance[inside]
        outcome = outcome[inside]
        weights = _kernel_weights(distance / bandwidth, kernel)
        keep = weights > 0.0
        distance = distance[keep]
        outcome = outcome[keep]
        weights = weights[keep]
        treated = (distance >= 0.0).astype(np.float64)
        n_right = int(treated.sum())
        n_left = int(treated.size - n_right)
        if n_left < 3 or n_right < 3:
            raise StepError("rdd: need at least three observations on each side of the cutoff")

        upper = distance * treated
        design = np.column_stack([np.ones(distance.size), distance, treated, upper])
        if np.linalg.matrix_rank(design) < design.shape[1]:
            raise StepError("rdd: local design matrix is rank deficient")
        xtwx = design.T @ (design * weights[:, None])
        bread = np.linalg.inv(xtwx)
        beta = bread @ (design.T @ (weights * outcome))
        resid = outcome - design @ beta
        meat = design.T @ (design * (weights * weights * resid * resid)[:, None])
        cov = bread @ meat @ bread
        tau = float(beta[2])
        se = float(np.sqrt(cov[2, 2]))
        if not np.isfinite(tau) or not np.isfinite(se) or se <= 0.0:
            raise StepError("rdd: the local estimate is not finite")
        zstat = tau / se
        pvalue = float(normal_p(np.asarray(zstat)))
        crit = float(stats.norm.ppf(0.5 + confidence / 2.0))
        rows = np.array([
            [tau],
            [se],
            [zstat],
            [pvalue],
            [tau - crit * se],
            [tau + crit * se],
            [n_left],
            [n_right],
            [bandwidth],
            [cutoff],
        ], dtype=np.float64)
        labels = {
            "statistic": {name: index for index, name in enumerate(
                ["tau", "se", "z", "p", "ci_low", "ci_high",
                 "n_left", "n_right", "bandwidth", "cutoff"])},
            "value": {"value": 0},
        }
        info = {
            "method": "local_linear",
            "kernel": kernel,
            "bandwidth": bandwidth,
            "cutoff": cutoff,
            "confidence": confidence,
            "n_obs_used": int(distance.size),
        }
        ctx[out_name] = make_form(rows, ["statistic", "value"], labels, info=info)

    def export(self, ctx: Context) -> dict:
        return {}
