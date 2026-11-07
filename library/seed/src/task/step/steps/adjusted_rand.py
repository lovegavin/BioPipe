"""Adjusted Rand index for two label columns."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import adjusted_rand_score

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._metric_common import label_series


class AdjustedRandStep(Step):
    provider = 'operon-core'
    """Adjusted Rand index between two label columns on the same samples."""
    parameters_file = 'adjusted_rand.AdjustedRandStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'adjusted_rand',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Adjusted Rand index',
     'category': 'Machine Learning',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
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
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Adjusted Rand index between two label columns on the same samples.'}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        label_dim = ctx.step_params.get("label_dim", "label")
        samples, true = label_series(form, sample_dim, label_dim, ctx.step_params["true_label"], "adjusted_rand")
        samples2, pred = label_series(form, sample_dim, label_dim, ctx.step_params["pred_label"], "adjusted_rand")
        if samples != samples2:
            raise StepError("adjusted_rand: label columns must share sample order")
        if len(samples) < 2:
            raise StepError("adjusted_rand: need at least two samples")
        score = float(adjusted_rand_score(true, pred))
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray([[score], [len(samples)]], dtype=np.float32),
            dims=["metric", "value"],
            labels={"metric": {"adjusted_rand": 0, "n_samples": 1}, "value": {"value": 0}},
            info={"missing_code": np.nan},
        )
        self._export_data = {"adjusted_rand": score, "n_samples": len(samples)}
        print(f"[adjusted_rand] ARI={score:.4f}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
