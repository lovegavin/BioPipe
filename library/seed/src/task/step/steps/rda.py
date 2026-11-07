"""Redundancy analysis of a response matrix explained by predictors."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._ext_common import reorder, require_dims


class RdaStep(Step):
    provider = 'operon-core'
    parameters_file = 'rda.RdaStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
        'id': 'rda',
        'version': '1.0.0',
        'kind': 'operator',
        'title': 'Redundancy analysis',
        'category': 'Statistics',
        'contracts': {
            'version': 1,
            'inputs': [
                {
                    'version': 1, 'numeric': True, 'info': {},
                    'dims': [{'param': 'sample_dim', 'default': 'sample'},
                             {'param': 'response_dim', 'default': 'response'}],
                    'labels': [], 'parallel': [], 'ndim': 2,
                },
                {
                    'version': 1, 'numeric': True, 'info': {},
                    'dims': [{'param': 'sample_dim', 'default': 'sample'},
                             {'param': 'predictor_dim', 'default': 'predictor'}],
                    'labels': [], 'parallel': [], 'ndim': 2,
                },
            ],
            'output': {'mode': 'declare',
                       'schema': {'ndim': 2, 'numeric': True,
                                  'info_open': True, 'axis_info_open': True}},
        },
        'resources': {'memory_modes': ['full'], 'supports_cuda': False,
                      'estimate': 'estimate_memory'},
        'dependencies': ['numpy>=1.24'],
        'dependency_imports': ['numpy'],
        'inputs_arity': 2,
        'outputs': [],
        'output_parameter': 'output',
        'description': 'Constrained ordination (RDA) of a response matrix on '
                       'centred predictors, returning constrained eigenvalues.',
    }

    def run(self, ctx: Context, inputs) -> None:
        response, explanatory = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        response_dim = ctx.step_params.get("response_dim", "response")
        predictor_dim = ctx.step_params.get("predictor_dim", "predictor")
        n_axes = int(ctx.step_params.get("n_axes", 4))
        out_name = ctx.step_params.get("output", self.name)
        if n_axes < 1:
            raise StepError("rda: n_axes must be at least 1")

        require_dims(response, sample_dim, response_dim, label="rda response")
        require_dims(explanatory, sample_dim, predictor_dim, label="rda predictors")
        r_labels = response.labels[sample_dim]
        e_labels = explanatory.labels[sample_dim]
        if set(r_labels) != set(e_labels):
            raise StepError("rda: response and predictors must share sample labels")
        names = list(r_labels)
        n = len(names)
        y = reorder(response, sample_dim, response_dim)
        x = reorder(explanatory, sample_dim, predictor_dim)
        y = y[[r_labels[name] for name in names]]
        x = x[[e_labels[name] for name in names]]
        if y.ndim != 2 or x.ndim != 2:
            raise StepError("rda: both inputs must be two-dimensional")
        if not np.all(np.isfinite(y)) or not np.all(np.isfinite(x)):
            raise StepError("rda: inputs must be finite")
        if n < 3:
            raise StepError("rda: need at least three samples")

        y = y - y.mean(axis=0, keepdims=True)
        x = x - x.mean(axis=0, keepdims=True)
        if np.allclose(x, 0.0):
            raise StepError("rda: predictors are constant")
        rank = np.linalg.matrix_rank(x)
        if rank == 0:
            raise StepError("rda: predictors carry no variation")

        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        fitted = x @ coef
        if not np.any(np.abs(fitted) > 0.0):
            raise StepError("rda: response is not explained by the predictors")
        _, singular, _ = np.linalg.svd(fitted / np.sqrt(n - 1), full_matrices=False)
        eigenvalues = singular ** 2
        scale = float(eigenvalues[0]) if eigenvalues.size else 0.0
        positive = eigenvalues > 1e-12 * scale
        eigenvalues = eigenvalues[positive]
        if eigenvalues.size == 0:
            raise StepError("rda: no constrained axes with positive eigenvalues")
        axes = min(n_axes, eigenvalues.size)
        eigenvalues = eigenvalues[:axes]
        total = float(eigenvalues.sum())
        proportion = eigenvalues / total
        cumulative = np.cumsum(proportion)

        data = np.empty((axes, 3), dtype=np.float64)
        data[:, 0] = eigenvalues
        data[:, 1] = proportion
        data[:, 2] = cumulative
        out = Form(
            data=data.astype(np.float32),
            dims=["axis", "statistic"],
            labels={"axis": {f"RDA{i + 1}": i for i in range(axes)},
                    "statistic": {"eigenvalue": 0, "proportion": 1,
                                  "cumulative": 2}},
            info={"missing_code": np.nan, "method": "redundancy analysis",
                  "n_samples": n, "predictor_rank": int(rank),
                  "eigenvalues": eigenvalues.tolist()},
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "eigenvalues": eigenvalues.tolist(),
            "proportion": proportion.tolist(),
            "rank": int(rank),
        }
        print(f"[rda] axes={axes}, eigenvalue1={eigenvalues[0]:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
