"""BIRCH hierarchical clustering by clustering features."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class BirchStep(Step):
    provider = 'operon-core'
    """Cluster samples with BIRCH (balanced iterative reducing and clustering)."""
    parameters_file = 'birch.BirchStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'birch',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'BIRCH clustering',
     'description': 'Balanced iterative reducing and clustering using hierarchies (BIRCH).',
     'category': 'Machine Learning',
     'icon': 'Sigma',
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
     'dependencies': ['scikit-learn>=1.5'],
     'dependency_imports': ['sklearn'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output'}

    def run(self, ctx: Context, inputs) -> None:
        from sklearn.cluster import Birch

        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        threshold = float(ctx.step_params.get("threshold", 0.5))
        branching_factor = int(ctx.step_params.get("branching_factor", 50))
        n_clusters = ctx.step_params.get("n_clusters")
        if threshold <= 0:
            raise StepError("birch: threshold must be > 0")
        if branching_factor < 2:
            raise StepError("birch: branching_factor must be >= 2")
        clusters = None
        if n_clusters is not None:
            clusters = int(n_clusters)
            if clusters < 2:
                raise StepError("birch: n_clusters must be >= 2 when given")
        X, sample_names, _ = matrix(form, sample_dim, feature_dim)
        model = Birch(
            threshold=threshold,
            branching_factor=branching_factor,
            n_clusters=clusters,
        )
        labels = model.fit_predict(X)
        samples = list(sample_names)
        n_clusters_found = len(set(labels.tolist()))
        out_name = ctx.step_params.get("output", self.name)
        ctx[out_name] = Form(
            data=labels.astype(np.float32).reshape(-1, 1),
            dims=[sample_dim, "cluster"],
            labels={
                sample_dim: {name: i for i, name in enumerate(samples)},
                "cluster": {"cluster": 0},
            },
            info={"missing_code": np.nan},
        )
        centers = np.asarray(model.subcluster_centers_, dtype=np.float64)
        self._export_data = {
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "n_clusters": n_clusters_found,
            "n_subclusters": int(centers.shape[0]),
            "subcluster_centers": centers.round(12).tolist(),
            "threshold": threshold,
            "branching_factor": branching_factor,
            "requested_n_clusters": clusters,
        }
        print(f"[birch] {len(samples)} samples -> {n_clusters_found} clusters, "
              f"{centers.shape[0]} subclusters")

    def export(self, ctx: Context) -> dict:
        return self._export_data
