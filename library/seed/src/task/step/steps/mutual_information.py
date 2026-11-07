"""Mutual information between each feature and a target label."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


class MutualInformationStep(Step):
    provider = 'operon-core'
    parameters_file = 'mutual_information.MutualInformationStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'mutual_information',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Mutual information',
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
     'description': 'Mutual information：接收 2 个输入，输出 Form；主要参数：样本维度、特征维度、标签维度、目标字段、Task、邻居数。'}

    def run(self, ctx: Context, inputs) -> None:
        try:
            from sklearn.feature_selection import mutual_info_classif, mutual_info_regression
        except ImportError as exc:
            raise StepError("mutual_information: scikit-learn is required") from exc
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        label_dim = ctx.step_params.get("label_dim", "label")
        x, samples, features = matrix(inputs[0], sample_dim, feature_dim)
        labels_form = inputs[1]
        if labels_form.data.ndim != 2 or sample_dim not in labels_form.dims or label_dim not in labels_form.dims:
            raise StepError(f"mutual_information: labels must have dims [{sample_dim!r}, {label_dim!r}], got {labels_form.dims}")
        columns = labels_form.labels.get(label_dim, {})
        target = ctx.step_params["target_label"]
        if target not in columns:
            raise StepError(f"mutual_information: target_label {target!r} not in {sorted(columns)}")
        axis = labels_form.dims.index(label_dim)
        y_raw = np.take(labels_form.data, list(range(len(labels_form.labels[sample_dim]))), axis=0)
        y_raw = np.take(y_raw, columns[target], axis=axis).reshape(len(labels_form.labels[sample_dim]))
        encoder = labels_form.info.get("encoders", {}).get(label_dim, {}).get(target)
        label_samples = labels_form.labels[sample_dim]
        sample_pos = {name: i for i, name in enumerate(samples)}
        label_pos = {name: i for i, name in enumerate(label_samples)}
        common = [name for name in samples if name in label_pos]
        if len(common) < 8:
            raise StepError(f"mutual_information: need at least 8 shared samples, got {len(common)}")
        X = x[[sample_pos[name] for name in common]]
        raw = np.array([y_raw[label_pos[name]] for name in common], dtype=np.float64)
        task = ctx.step_params.get("task", "classification")
        if task == "classification":
            y = []
            for value in raw:
                if not np.isfinite(value):
                    y.append(None)
                elif encoder is not None:
                    y.append(str(encoder.inverse.get(int(round(float(value))), "")))
                else:
                    y.append(str(int(round(float(value)))))
            keep = np.array([v is not None and v != "" for v in y])
            if keep.sum() < 8:
                raise StepError(f"mutual_information: only {int(keep.sum())} labelled samples")
            classes = sorted(set(v for v, k in zip(y, keep) if k))
            if len(classes) < 2:
                raise StepError(f"mutual_information: need >= 2 classes, got {classes}")
            yy = np.array([classes.index(v) for v in y if v is not None and v != ""])
        else:
            if encoder is not None:
                recovered = []
                for value in raw:
                    if not np.isfinite(value):
                        recovered.append(np.nan)
                        continue
                    try:
                        recovered.append(float(encoder.inverse.get(int(round(float(value))))))
                    except (TypeError, ValueError):
                        recovered.append(np.nan)
                raw = np.asarray(recovered, dtype=np.float64)
            keep = np.isfinite(raw)
            if keep.sum() < 8:
                raise StepError(f"mutual_information: only {int(keep.sum())} numeric targets")
            yy = raw[keep]
        X = X[keep]
        X = np.where(np.isfinite(X), X, 0.0)
        if task == "classification":
            scores = mutual_info_classif(X, yy, n_neighbors=int(ctx.step_params.get("n_neighbors", 3)), random_state=int(ctx.step_params.get("random_state", 0)))
        else:
            scores = mutual_info_regression(X, yy, n_neighbors=int(ctx.step_params.get("n_neighbors", 3)), random_state=int(ctx.step_params.get("random_state", 0)))
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(scores, dtype=np.float32).reshape(-1, 1), dims=[feature_dim, "statistic"],
            labels={feature_dim: {name: i for i, name in enumerate(features)}, "statistic": {"score": 0}},
            info={"task": task, "n_neighbors": int(ctx.step_params.get("n_neighbors", 3))},
        )
        self._export = {"n_samples": int(keep.sum()), "n_features": len(features), "task": task}
        print(f"[{self.name}] {self._export}")

    def export(self, ctx: Context) -> dict:
        return self._export
