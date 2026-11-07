"""Homogeneity, completeness, and V-measure for two label columns."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import homogeneity_completeness_v_measure

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._cluster_agreement import paired_labels


class HomogeneityCompletenessVMeasureStep(Step):
    provider = 'operon-core'
    """Three entropy-based agreement scores for two partitions."""
    parameters_file = 'homogeneity_completeness_v_measure.HomogeneityCompletenessVMeasureStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'homogeneity_completeness_v_measure',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Homogeneity, completeness, V-measure',
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
     'description': 'Three entropy-based agreement scores for two partitions.'}


    def run(self, ctx: Context, inputs) -> None:
        first, second = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        label_dim = ctx.step_params.get("label_dim", "label")
        beta = float(ctx.step_params.get("beta", 1.0))
        left, right = paired_labels(
            first,
            second,
            sample_dim,
            label_dim,
            ctx.step_params["label_a"],
            ctx.step_params["label_b"],
            "homogeneity_completeness_v_measure",
        )
        n_a, n_b = len(set(left)), len(set(right))
        if n_a < 2 or n_b < 2:
            raise StepError(
                "homogeneity_completeness_v_measure: need at least two clusters in each partition"
            )
        homogeneity, completeness, v_measure = homogeneity_completeness_v_measure(
            left, right, beta=beta
        )
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(
                [
                    [homogeneity],
                    [completeness],
                    [v_measure],
                    [len(left)],
                    [n_a],
                    [n_b],
                ],
                dtype=np.float32,
            ),
            dims=["metric", "value"],
            labels={
                "metric": {
                    "homogeneity": 0,
                    "completeness": 1,
                    "v_measure": 2,
                    "n_samples": 3,
                    "n_clusters_a": 4,
                    "n_clusters_b": 5,
                },
                "value": {"value": 0},
            },
            info={"missing_code": np.nan, "beta": beta},
        )
        self._export_data = {
            "homogeneity": float(homogeneity),
            "completeness": float(completeness),
            "v_measure": float(v_measure),
            "beta": beta,
            "n_samples": len(left),
            "n_clusters_a": n_a,
            "n_clusters_b": n_b,
        }
        print(
            f"[homogeneity_completeness_v_measure] h={homogeneity:.4f}, "
            f"c={completeness:.4f}, v={v_measure:.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
