"""Gower distance for mixed numeric and categorical features."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, make_form, reorder


class GowerDistanceStep(Step):
    provider = 'operon-core'
    parameters_file = 'gower_distance.GowerDistanceStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'gower_distance',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Gower distance',
     'category': 'Statistics',
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
                                         'axis_info_open': False}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.26'],
     'dependency_imports': ['numpy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': ('Gower distance：数值列按极差归一、分类列按相等与否取 0/1，'
                     '缺失变量在每对样本间重新归一，输出对称距离矩阵。')}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_b_dim = ctx.step_params.get("sample_b_dim", "sample_b")
        categorical = ctx.step_params.get("categorical_labels") or []
        out_name = ctx.step_params.get("output", self.name)
        if not isinstance(categorical, (list, tuple)):
            raise StepError("gower_distance: 'categorical_labels' must be a list")
        matrix = reorder(form, sample_dim, feature_dim)
        samples = labels_in_order(form, sample_dim)
        features = labels_in_order(form, feature_dim)
        if matrix.shape[0] < 2:
            raise StepError("gower_distance: at least two samples are required")
        known = {name: position for position, name in enumerate(features)}
        categorical_positions = set()
        for name in categorical:
            if name not in known:
                raise StepError(f"gower_distance: categorical label {name!r} not found")
            categorical_positions.add(known[name])
        data = np.asarray(matrix, dtype=np.float64)
        numeric_positions = [j for j in range(len(features))
                             if j not in categorical_positions]
        ranges = {}
        for j in numeric_positions:
            column = data[:, j]
            finite = column[np.isfinite(column)]
            ranges[j] = None if finite.size == 0 else float(finite.max() - finite.min())
        n = data.shape[0]
        block = max(1, min(n, 512))
        numerator = np.zeros((n, n), dtype=np.float64)
        weights = np.zeros((n, n), dtype=np.float64)
        for start in range(0, n, block):
            stop = min(n, start + block)
            part = np.zeros((stop - start, n), dtype=np.float64)
            counts = np.zeros((stop - start, n), dtype=np.float64)
            for j in numeric_positions:
                column = data[:, j]
                values = column[start:stop]
                present = np.isfinite(values)[:, None] & np.isfinite(column)[None, :]
                difference = np.abs(values[:, None] - column[None, :])
                span = ranges[j]
                term = np.zeros_like(difference) if not span else difference / span
                part += np.where(present, term, 0.0)
                counts += present
            for j in sorted(categorical_positions):
                column = data[:, j]
                values = column[start:stop]
                present = np.isfinite(values)[:, None] & np.isfinite(column)[None, :]
                term = (values[:, None] != column[None, :]).astype(np.float64)
                part += np.where(present, term, 0.0)
                counts += present
            numerator[start:stop] = part
            weights[start:stop] = counts
        with np.errstate(invalid="ignore", divide="ignore"):
            distance = np.where(weights > 0, numerator / weights, np.nan)
        distance = 0.5 * (distance + distance.T)
        np.fill_diagonal(distance, 0.0)
        labels = {dim: {name: i for i, name in enumerate(names)}
                  for dim, names in ((sample_dim, samples), (sample_b_dim, samples))}
        out = make_form(distance, [sample_dim, sample_b_dim], labels)
        ctx[out_name] = out
        self._export_data = {
            "n_samples": int(n),
            "n_features": int(data.shape[1]),
            "numeric_features": [features[j] for j in numeric_positions],
            "categorical_features": [features[j] for j in sorted(categorical_positions)],
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
