"""Agglomerative hierarchical clustering with SciPy linkage."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


_METHODS = {
    "single": "single",
    "complete": "complete",
    "average": "average",
    "ward.D2": "ward",
}
_METRICS = {"euclidean": "euclidean", "manhattan": "cityblock"}


def _ordered(labels: dict) -> list[str]:
    return [name for name, _ in sorted(labels.items(), key=lambda item: item[1])]


class HierarchicalClusteringStep(Step):
    provider = 'operon-core'
    """Cluster samples with single/complete/average/Ward linkage."""
    parameters_file = 'hierarchical_clustering.HierarchicalClusteringStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'hierarchical_clustering',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Hierarchical clustering',
     'category': 'Machine Learning',
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
     'dependencies': ['scipy>=1.11'],
     'dependency_imports': ['scipy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Cluster samples with single/complete/average/Ward linkage.'}



    def run(self, ctx: Context, inputs) -> None:
        from scipy.cluster.hierarchy import cophenet, cut_tree, linkage
        from scipy.spatial.distance import pdist

        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        n_clusters = int(ctx.step_params.get("n_clusters", 3))
        method = ctx.step_params.get("linkage", "average")
        metric = ctx.step_params.get("metric", "euclidean")

        if form.data.ndim != 2:
            raise StepError("hierarchical_clustering: expected a 2D form")
        for dim in (sample_dim, feature_dim):
            if dim not in form.dims:
                raise StepError(
                    f"hierarchical_clustering: dim {dim!r} not in {form.dims}"
                )
        if method not in _METHODS:
            raise StepError(
                f"hierarchical_clustering: linkage must be one of {sorted(_METHODS)}"
            )
        if metric not in _METRICS:
            raise StepError(
                f"hierarchical_clustering: metric must be one of {sorted(_METRICS)}"
            )

        axis = form.dims.index(sample_dim)
        X = np.moveaxis(np.asarray(form.data), axis, 0).astype(np.float64)
        if X.shape[0] < 3:
            raise StepError("hierarchical_clustering: need at least three samples")
        if X.shape[1] < 1:
            raise StepError("hierarchical_clustering: need at least one feature")
        if not np.isfinite(X).all():
            raise StepError("hierarchical_clustering: input contains non-finite values")
        if n_clusters < 2 or n_clusters >= X.shape[0]:
            raise StepError(
                "hierarchical_clustering: n_clusters must be in [2, n_samples - 1]"
            )

        distances = pdist(X, metric=_METRICS[metric])
        tree = linkage(distances, method=_METHODS[method])
        labels = [
            int(value) for value in cut_tree(tree, n_clusters=n_clusters).ravel().tolist()
        ]
        if len(set(labels)) < n_clusters:
            raise StepError(
                "hierarchical_clustering: could not form distinct clusters; "
                "check for duplicate samples or reduce n_clusters"
            )

        sample_names = _ordered(form.labels[sample_dim])
        output = ctx.step_params.get("output", self.name)
        ctx[output] = Form(
            data=np.asarray(labels, dtype=np.float32).reshape(-1, 1),
            dims=[sample_dim, "cluster"],
            labels={
                sample_dim: {name: index for index, name in enumerate(sample_names)},
                "cluster": {"cluster": 0},
            },
            info={"missing_code": np.nan},
        )

        heights = [float(value) for value in tree[:, 2].tolist()]
        merge = [
            [int(row[0]), int(row[1]), float(row[2]), int(row[3])]
            for row in tree.tolist()
        ]
        correlation = float(cophenet(tree, distances)[0])
        self._export_data = {
            "method": "hierarchical_clustering",
            "linkage": method,
            "metric": metric,
            "n_clusters": n_clusters,
            "n": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "labels": labels,
            "heights": heights,
            "merge": merge,
            "cophenetic_correlation": correlation,
        }
        print(
            f"[hierarchical_clustering] {X.shape[0]} samples, "
            f"{method}/{metric}, {n_clusters} clusters"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
