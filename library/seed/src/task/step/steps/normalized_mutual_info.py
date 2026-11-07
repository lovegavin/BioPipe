"""Normalized mutual information for two cluster-label columns."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import normalized_mutual_info_score

from src.core import Form
from src.task.context import Context
from src.task.step.base import Step
from ._cluster_agreement import paired_labels


class NormalizedMutualInfoStep(Step):
    provider = 'operon-core'
    """Normalized mutual information between two partitions."""
    parameters_file = 'normalized_mutual_info.NormalizedMutualInfoStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'normalized_mutual_info',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Normalized mutual information',
     'category': 'Machine Learning',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'label_dim', 'default': 'label'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2},
                              {'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'label_dim', 'default': 'label'}],
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
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Normalized mutual information between two partitions.'}


    def run(self, ctx: Context, inputs) -> None:
        first, second = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        label_dim = ctx.step_params.get("label_dim", "label")
        method = ctx.step_params.get("average_method", "arithmetic")
        left, right = paired_labels(
            first,
            second,
            sample_dim,
            label_dim,
            ctx.step_params["label_a"],
            ctx.step_params["label_b"],
            "normalized_mutual_info",
        )
        score = float(normalized_mutual_info_score(left, right, average_method=method))
        n_a, n_b = len(set(left)), len(set(right))
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray([[score], [len(left)], [n_a], [n_b]], dtype=np.float32),
            dims=["metric", "value"],
            labels={
                "metric": {
                    "normalized_mutual_info": 0,
                    "n_samples": 1,
                    "n_clusters_a": 2,
                    "n_clusters_b": 3,
                },
                "value": {"value": 0},
            },
            info={"missing_code": np.nan, "average_method": method},
        )
        self._export_data = {
            "normalized_mutual_info": score,
            "n_samples": len(left),
            "n_clusters_a": n_a,
            "n_clusters_b": n_b,
            "average_method": method,
        }
        print(f"[normalized_mutual_info] {score:.4f} ({method})")

    def export(self, ctx: Context) -> dict:
        return self._export_data
