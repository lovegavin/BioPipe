"""ROC curve for binary labels and a numeric score."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import roc_curve

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._metric_common import binary_truth, label_series, score_series


class RocCurveStep(Step):
    provider = 'operon-core'
    """ROC curve points (FPR, TPR, threshold) for a binary target."""
    parameters_file = 'roc_curve.RocCurveStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'roc_curve',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'ROC curve',
     'category': 'Statistics',
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
                                        {'param': 'score_dim', 'default': 'score'}],
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
     'description': 'ROC curve points (FPR, TPR, threshold) for a binary target.'}


    def run(self, ctx: Context, inputs) -> None:
        label_form, score_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        label_dim = ctx.step_params.get("label_dim", "label")
        score_dim = ctx.step_params.get("score_dim", "score")
        label_samples, labels = label_series(label_form, sample_dim, label_dim, ctx.step_params["target_label"], "roc_curve")
        score_samples, scores = score_series(
            score_form, sample_dim, score_dim,
            ctx.step_params.get("score_label") or next(iter(score_form.labels[score_dim])),
        )
        pos = {name: i for i, name in enumerate(score_samples)}
        keep = [i for i, name in enumerate(label_samples) if name in pos]
        if len(keep) < 4:
            raise StepError("roc_curve: fewer than four shared samples")
        y_labels = [labels[i] for i in keep]
        y_scores = np.asarray([scores[pos[label_samples[i]]] for i in keep], dtype=np.float64)
        classes, positive, y_true = binary_truth(label_samples, y_labels, ctx.step_params.get("positive_label"))
        fpr, tpr, thresholds = roc_curve(y_true, y_scores, drop_intermediate=False)
        data = np.column_stack([fpr, tpr, thresholds]).astype(np.float32)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=data,
            dims=["threshold", "statistic"],
            labels={
                "threshold": {f"t{i}": i for i in range(data.shape[0])},
                "statistic": {"fpr": 0, "tpr": 1, "threshold": 2},
            },
            info={"missing_code": np.nan, "positive_label": positive, "classes": classes},
        )
        self._export_data = {"n_samples": len(y_true), "n_points": int(data.shape[0]), "positive_label": positive}
        print(f"[roc_curve] n={len(y_true)}, points={data.shape[0]}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
