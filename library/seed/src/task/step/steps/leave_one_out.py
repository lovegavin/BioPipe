"""Leave-one-study-out sensitivity analysis for inverse-variance meta-analysis."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._multivariate35_common import frame_matrix

_STATISTICS = [
    "estimate",
    "se",
    "z",
    "p",
    "ci_low",
    "ci_high",
    "tau2",
    "I2",
    "Q",
    "Qp",
    "k",
]


def _pooled(effect: np.ndarray, variance: np.ndarray, method: str):
    weights = 1.0 / variance
    fixed = float(np.sum(weights * effect) / np.sum(weights))
    fixed_se = float(np.sqrt(1.0 / np.sum(weights)))
    k = effect.size
    q = float(np.sum(weights * (effect - fixed) ** 2))
    df = k - 1
    tau2 = 0.0
    if method == "random":
        denominator = float(np.sum(weights) - np.sum(weights**2) / np.sum(weights))
        tau2 = max(0.0, (q - df) / denominator) if denominator > 0 else 0.0
        random_weights = 1.0 / (variance + tau2)
        estimate = float(np.sum(random_weights * effect) / np.sum(random_weights))
        se = float(np.sqrt(1.0 / np.sum(random_weights)))
    else:
        estimate, se = fixed, fixed_se
    i2 = 100.0 * max(0.0, (q - df) / q) if q > 0 else 0.0
    qp = float(stats.chi2.sf(q, df))
    return estimate, se, tau2, i2, q, qp


class LeaveOneOutStep(Step):
    provider = 'operon-core'
    """Refit an intercept-only meta-analysis after omitting each study."""
    parameters_file = 'leave_one_out.LeaveOneOutStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'leave_one_out',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Leave-one-out meta-analysis',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'study_dim', 'default': 'study'},
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
     'dependencies': ['numpy>=1.26', 'scipy>=1.11'],
     'dependency_imports': ['numpy', 'scipy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Refit an intercept-only meta-analysis after omitting each study.'}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        study_dim = ctx.step_params.get("study_dim", "study")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        effect_label = ctx.step_params["effect_label"]
        variance_label = ctx.step_params["variance_label"]
        if effect_label == variance_label:
            raise StepError("leave_one_out: effect and variance columns must differ")
        method = ctx.step_params.get("method", "random")
        confidence = float(ctx.step_params.get("confidence", 0.95))
        samples, _names, values = frame_matrix(
            form,
            study_dim,
            feature_dim,
            "leave_one_out",
            columns=[effect_label, variance_label],
        )
        if len(set(samples)) != len(samples):
            raise StepError("leave_one_out: study labels must be unique")
        if values.shape[0] < 3:
            raise StepError("leave_one_out: need at least three studies")
        effect = values[:, 0]
        variance = values[:, 1]
        if not np.isfinite(effect).all() or not np.isfinite(variance).all():
            raise StepError("leave_one_out: effect and variance values must be finite")
        if np.any(variance <= 0):
            raise StepError("leave_one_out: variances must be positive")

        rows = []
        omitted = []
        for index, name in enumerate(samples):
            keep = np.ones(effect.size, dtype=bool)
            keep[index] = False
            estimate, se, tau2, i2, q, qp = _pooled(
                effect[keep], variance[keep], method
            )
            z = estimate / se if se > 0 else np.nan
            p = float(2.0 * stats.norm.sf(abs(z))) if np.isfinite(z) else np.nan
            critical = float(stats.norm.ppf(0.5 + confidence / 2.0))
            rows.append(
                [
                    estimate,
                    se,
                    z,
                    p,
                    estimate - critical * se,
                    estimate + critical * se,
                    tau2,
                    i2,
                    q,
                    qp,
                    int(keep.sum()),
                ]
            )
            omitted.append(name)

        table = np.asarray(rows, dtype=np.float64)
        output = ctx.step_params.get("output", self.name)
        ctx[output] = Form(
            data=table,
            dims=[study_dim, "statistic"],
            labels={
                study_dim: {name: index for index, name in enumerate(omitted)},
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "method": method,
                "n_studies": int(effect.size),
                "confidence": confidence,
            },
        )
        self._export_data = {
            "method": method,
            "n_studies": int(effect.size),
            "confidence": confidence,
            "results": [
                {
                    "omitted": name,
                    **{
                        column: float(value)
                        for column, value in zip(_STATISTICS, row)
                    },
                }
                for name, row in zip(omitted, table)
            ],
        }
        print(f"[leave_one_out] {effect.size} studies, method={method}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
