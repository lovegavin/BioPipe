"""Chao1 richness estimator for a sample-by-feature count table."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._multivariate35_common import frame_matrix


class Chao1Step(Step):
    provider = 'operon-core'
    """Estimate the number of unobserved species with the Chao1 estimator."""
    parameters_file = 'chao1.Chao1Step.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'chao1',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Chao1 richness estimator',
     'category': 'Omics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
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
     'dependencies': ['numpy>=1.26'],
     'dependency_imports': ['numpy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Estimate the number of unobserved species with the Chao1 estimator.'}


    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        samples, features, matrix = frame_matrix(
            inputs[0], sample_dim, feature_dim, self.name
        )
        if matrix.shape[0] == 0:
            raise StepError("chao1: input has no samples")
        if not np.isfinite(matrix).all():
            raise StepError("chao1: counts must be finite")
        if (matrix < 0).any():
            raise StepError("chao1: counts must be non-negative")
        if not np.allclose(matrix, np.floor(matrix)):
            raise StepError("chao1: counts must be integers")

        observed = (matrix > 0).sum(axis=1).astype(np.float64)
        totals = matrix.sum(axis=1).astype(np.float64)
        singletons = (matrix == 1).sum(axis=1).astype(np.float64)
        doubletons = (matrix == 2).sum(axis=1).astype(np.float64)
        with np.errstate(divide="ignore", invalid="ignore"):
            classic = observed + singletons * singletons / (2.0 * doubletons)
        bias_corrected = observed + singletons * (singletons - 1.0) / 2.0
        chao1 = np.where(doubletons > 0, classic, bias_corrected)
        chao1 = np.where(totals > 0, chao1, 0.0)

        data = np.column_stack([chao1, observed, singletons, doubletons, totals])
        names = ["chao1", "observed", "singletons", "doubletons", "n"]
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=data.astype(np.float32),
            dims=["sample", "statistic"],
            labels={
                "sample": {name: i for i, name in enumerate(samples)},
                "statistic": {name: i for i, name in enumerate(names)},
            },
            info={
                "method": "chao1",
                "n_samples": len(samples),
                "n_features": len(features),
            },
        )

        self._export = {
            "samples": samples,
            "features": features,
            "chao1": chao1.tolist(),
            "observed": observed.tolist(),
            "singletons": singletons.tolist(),
            "doubletons": doubletons.tolist(),
            "n": totals.tolist(),
        }
        print(f"[{self.name}] samples={len(samples)}, features={len(features)}")

    def export(self, ctx: Context) -> dict:
        return self._export
