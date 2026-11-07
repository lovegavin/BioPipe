"""Non-metric multidimensional scaling (NMDS).

NMDS finds a low-dimensional configuration whose rank order of inter-point
distances best matches the observed dissimilarities.  The implementation uses
scikit-learn's SMACOF solver with a deterministic classical-MDS start.  Stress
is reported as raw Kruskal stress and as stress-1 (normalised by the observed
squared distances).
"""
from __future__ import annotations

import inspect
import math

import numpy as np
from sklearn.manifold import MDS

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import distance


class NmdsStep(Step):
    provider = 'operon-core'
    """Non-metric multidimensional scaling from a dissimilarity matrix."""
    parameters_file = 'nmds.NmdsStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'nmds',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Non-metric multidimensional scaling',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'sample_b_dim', 'default': 'sample_b'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.26', 'scikit-learn>=1.3'],
     'dependency_imports': ['numpy', 'sklearn'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Non-metric multidimensional scaling from a dissimilarity matrix.'}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        sample_b_dim = ctx.step_params.get("sample_b_dim", "sample_b")
        D, samples = distance(form, sample_dim, sample_b_dim, self.name)
        n = len(samples)
        if n < 3:
            raise StepError(f"{self.name}: at least three samples are required")
        if not np.allclose(np.diag(D), 0.0, atol=1e-12):
            raise StepError(f"{self.name}: distance matrix diagonal must be zero")
        if np.any(D < 0):
            raise StepError(f"{self.name}: distances must be nonnegative")
        if not np.any(D > 0):
            raise StepError(f"{self.name}: distance matrix must contain positive distances")

        components = int(ctx.step_params.get("n_components", 2))
        if components >= n:
            raise StepError(
                f"{self.name}: n_components ({components}) must be smaller than "
                f"the number of samples ({n})"
            )
        max_iter = int(ctx.step_params.get("max_iter", 300))
        eps = float(ctx.step_params.get("eps", 1e-9))
        if eps <= 0:
            raise StepError(f"{self.name}: eps must be positive")

        parameters = inspect.signature(MDS.__init__).parameters
        candidate = {
            "n_components": components,
            "init": "classical_mds",
            "n_init": 10,
            "max_iter": max_iter,
            "eps": eps,
            "normalized_stress": False,
            "random_state": 0,
        }
        if "metric_mds" in parameters:
            candidate["metric_mds"] = False
            candidate["metric"] = "precomputed"
        else:  # pragma: no cover - older scikit-learn
            candidate["metric"] = False
            candidate["dissimilarity"] = "precomputed"
        # scikit-learn removes and renames MDS keywords between minor releases.
        kwargs = {key: value for key, value in candidate.items() if key in parameters}

        model = MDS(**kwargs).fit(D)
        coords = np.asarray(model.embedding_, dtype=np.float64)
        if coords.shape != (n, components) or not np.isfinite(coords).all():
            raise StepError(f"{self.name}: NMDS produced an invalid embedding")

        # Rotations/reflections are arbitrary; fix each axis sign deterministically
        # so repeated runs on the same input produce the same table.
        for axis in range(components):
            anchor = int(np.argmax(np.abs(coords[:, axis])))
            if coords[anchor, axis] < 0:
                coords[:, axis] *= -1.0

        stress = max(0.0, float(model.stress_))
        total = float(np.sum(D * D))
        stress1 = math.sqrt(stress / total) if total > 0 else float("nan")
        if not math.isfinite(stress1):
            raise StepError(f"{self.name}: could not compute finite stress")

        out = Form(
            data=coords,
            dims=[sample_dim, "component"],
            labels={
                sample_dim: {name: index for index, name in enumerate(samples)},
                "component": {
                    f"NMDS{index + 1}": index for index in range(components)
                },
            },
            info={
                "method": "nmds",
                "metric": False,
                "init": "classical_mds",
                "n": int(n),
                "n_components": int(components),
                "n_iter": int(model.n_iter_),
                "stress": stress,
                "stress1": stress1,
                "stress_percent": 100.0 * stress1,
                "max_iter": max_iter,
                "eps": eps,
            },
        )
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export = {
            "samples": samples,
            "coordinates": coords.tolist(),
            "stress": stress,
            "stress1": stress1,
            "stress_percent": 100.0 * stress1,
            "n": int(n),
            "n_components": int(components),
            "n_iter": int(model.n_iter_),
        }
        print(f"[{self.name}] n={n}, components={components}, stress1={stress1:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
