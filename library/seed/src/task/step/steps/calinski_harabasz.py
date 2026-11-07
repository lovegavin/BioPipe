"""Calinski-Harabasz clustering validity index."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import calinski_harabasz_score

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix
from ._metric_common import label_series


class CalinskiHarabaszStep(Step):
    provider = 'operon-core'
    """Calinski-Harabasz index for features and a label column."""
    parameters_file = 'calinski_harabasz.CalinskiHarabaszStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'calinski_harabasz',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Calinski-Harabasz index',
     'category': 'Machine Learning',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'sample_dim', 'default': 'sample'},
                                        {'param': 'feature_dim', 'default': 'feature'}],
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
     'description': 'Calinski-Harabasz index for features and a label column.'}


    def run(self, ctx: Context, inputs) -> None:
        feature_form, label_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        label_dim = ctx.step_params.get("label_dim", "label")
        X, samples, _ = matrix(feature_form, sample_dim, feature_dim)
        label_samples, labels = label_series(label_form, sample_dim, label_dim, ctx.step_params["target_label"], "calinski_harabasz")
        pos = {name: i for i, name in enumerate(label_samples)}
        keep = [i for i, name in enumerate(samples) if name in pos]
        if len(keep) < 4:
            raise StepError("calinski_harabasz: fewer than four shared samples")
        y = [labels[pos[samples[i]]] for i in keep]
        classes = sorted(set(y))
        if len(classes) < 2:
            raise StepError("calinski_harabasz: need at least two clusters")
        score = float(calinski_harabasz_score(X[keep], y))
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray([[score], [len(keep)], [len(classes)]], dtype=np.float32),
            dims=["metric", "value"],
            labels={"metric": {"calinski_harabasz": 0, "n_samples": 1, "n_clusters": 2}, "value": {"value": 0}},
            info={"missing_code": np.nan},
        )
        self._export_data = {"calinski_harabasz": score, "n_samples": len(keep), "n_clusters": len(classes)}
        print(f"[calinski_harabasz] {score:.4f}, k={len(classes)}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
