"""HDBSCAN hierarchical density-based clustering."""

from __future__ import annotations

import warnings

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class HdbscanStep(Step):
    provider = 'operon-core'
    """Cluster samples with HDBSCAN and report membership probabilities."""
    parameters_file = 'hdbscan.HdbscanStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'hdbscan',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'HDBSCAN clustering',
     'description': 'Hierarchical density-based clustering with cluster membership probabilities.',
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
        from sklearn.cluster import HDBSCAN

        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        min_cluster_size = int(ctx.step_params.get("min_cluster_size", 5))
        min_samples = ctx.step_params.get("min_samples")
        epsilon = float(ctx.step_params.get("cluster_selection_epsilon", 0.0))
        method = ctx.step_params.get("cluster_selection_method", "eom")
        metric = ctx.step_params.get("metric", "euclidean")
        if min_cluster_size < 2:
            raise StepError("hdbscan: min_cluster_size must be >= 2")
        samples_count = None
        if min_samples is not None:
            samples_count = int(min_samples)
            if samples_count < 1:
                raise StepError("hdbscan: min_samples must be >= 1 when given")
        if epsilon < 0:
            raise StepError("hdbscan: cluster_selection_epsilon must be >= 0")
        if method not in ("eom", "leaf"):
            raise StepError("hdbscan: cluster_selection_method must be 'eom' or 'leaf'")
        X, sample_names, _ = matrix(form, sample_dim, feature_dim)
        kwargs = {
            "min_cluster_size": min_cluster_size,
            "min_samples": samples_count,
            "cluster_selection_epsilon": epsilon,
            "cluster_selection_method": method,
            "metric": metric,
        }
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            try:
                model = HDBSCAN(copy=True, **kwargs).fit(X)
            except TypeError:  # scikit-learn < 1.9 has no ``copy`` keyword
                model = HDBSCAN(**kwargs).fit(X)
        labels = np.asarray(model.labels_, dtype=np.int64)
        probabilities = np.asarray(model.probabilities_, dtype=np.float64)
        samples = list(sample_names)
        data = np.column_stack([labels.astype(np.float64), probabilities])
        out_name = ctx.step_params.get("output", self.name)
        ctx[out_name] = Form(
            data=data.astype(np.float32),
            dims=[sample_dim, "statistic"],
            labels={
                sample_dim: {name: i for i, name in enumerate(samples)},
                "statistic": {"cluster": 0, "probability": 1},
            },
            info={"missing_code": np.nan},
        )
        n_clusters = len(set(labels.tolist())) - (1 if -1 in labels else 0)
        self._export_data = {
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "n_clusters": n_clusters,
            "n_noise": int((labels == -1).sum()),
            "min_cluster_size": min_cluster_size,
            "min_samples": samples_count,
            "cluster_selection_epsilon": epsilon,
            "cluster_selection_method": method,
            "metric": metric,
        }
        print(f"[hdbscan] {len(samples)} samples -> {n_clusters} clusters, "
              f"{int((labels == -1).sum())} noise")

    def export(self, ctx: Context) -> dict:
        return self._export_data
