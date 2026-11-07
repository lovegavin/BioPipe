"""OPTICS density-based ordering and clustering."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class OpticsStep(Step):
    provider = 'operon-core'
    """Order samples by reachability and extract density clusters with OPTICS."""
    parameters_file = 'optics.OpticsStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'optics',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'OPTICS clustering',
     'description': 'Ordering points to identify clustering structure (OPTICS).',
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
        from sklearn.cluster import OPTICS

        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        min_samples = int(ctx.step_params.get("min_samples", 5))
        max_eps = ctx.step_params.get("max_eps")
        xi = float(ctx.step_params.get("xi", 0.05))
        metric = ctx.step_params.get("metric", "euclidean")
        if min_samples < 2:
            raise StepError("optics: min_samples must be >= 2")
        if not 0.0 < xi < 1.0:
            raise StepError("optics: xi must be in (0, 1)")
        if max_eps is not None and float(max_eps) <= 0:
            raise StepError("optics: max_eps must be > 0 when given")
        X, sample_names, _ = matrix(form, sample_dim, feature_dim)
        model = OPTICS(
            min_samples=min_samples,
            max_eps=np.inf if max_eps is None else float(max_eps),
            xi=xi,
            metric=metric,
        )
        labels = model.fit_predict(X)
        reachability = np.asarray(model.reachability_, dtype=np.float64)
        core = np.asarray(model.core_distances_, dtype=np.float64)
        infinite = int(np.isinf(reachability).sum())
        reachability = np.where(np.isinf(reachability), np.nan, reachability)
        samples = list(sample_names)
        data = np.column_stack([labels.astype(np.float64), reachability, core])
        out_name = ctx.step_params.get("output", self.name)
        ctx[out_name] = Form(
            data=data.astype(np.float32),
            dims=[sample_dim, "statistic"],
            labels={
                sample_dim: {name: i for i, name in enumerate(samples)},
                "statistic": {"cluster": 0, "reachability": 1, "core_distance": 2},
            },
            info={"missing_code": np.nan},
        )
        n_clusters = len(set(labels.tolist())) - (1 if -1 in labels else 0)
        self._export_data = {
            "n_samples": int(X.shape[0]),
            "n_features": int(X.shape[1]),
            "n_clusters": n_clusters,
            "n_noise": int((labels == -1).sum()),
            "min_samples": min_samples,
            "max_eps": None if max_eps is None else float(max_eps),
            "xi": xi,
            "metric": metric,
            "cluster_method": "xi",
            "infinite_reachability": infinite,
            "ordering": [int(v) for v in model.ordering_],
        }
        print(f"[optics] {len(samples)} samples -> {n_clusters} clusters, "
              f"{int((labels == -1).sum())} noise")

    def export(self, ctx: Context) -> dict:
        return self._export_data
