"""Moran's I spatial autocorrelation.

``observed``, ``expected``, the normality standard deviation and the
two-sided p-value follow ``ape::Moran.I``: weights are divided by their
row sums, ``I = (n / S0) * (y' W y) / (y' y)`` and the variance uses the
S1/S2 sums and the sample kurtosis.
"""
from __future__ import annotations

from statistics import NormalDist

import numpy as np

from src.core import StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, reorder, require_dims
from ._stats20_common import distance, scalar_form


def _single_column(form, sample_dim, feature_dim, value_label):
    require_dims(form, sample_dim, feature_dim, label="moran")
    samples = labels_in_order(form, sample_dim)
    features = labels_in_order(form, feature_dim)
    data = reorder(form, sample_dim, feature_dim)
    if value_label:
        if value_label not in features:
            raise StepError(f"moran: value column {value_label!r} not found")
        column = features.index(value_label)
    else:
        if len(features) != 1:
            raise StepError(
                "moran: input must have exactly one value column, or set value_label"
            )
        column = 0
    values = np.asarray(data[:, column], dtype=np.float64)
    if values.size < 4:
        raise StepError("moran: need at least four samples")
    if not np.isfinite(values).all():
        raise StepError("moran: values must be finite")
    return samples, values


class MoranStep(Step):
    """Moran's I for one value column and one distance matrix."""

    provider = 'operon-core'
    parameters_file = 'moran.MoranStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'moran',
     'version': '1.0.0',
     'kind': 'operator',
     'title': "Moran's I",
     'category': 'Statistics',
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
                                        {'param': 'sample_b_dim', 'default': 'sample_b'}],
                               'labels': [],
                               'parallel': [],
                               'ndim': 2}],
                   'output': {'mode': 'declare',
                              'schema': {'ndim': 2,
                                         'numeric': True,
                                         'info_open': True,
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.26'],
     'dependency_imports': ['numpy'],
     'inputs_arity': 2,
     'outputs': [],
     'output_parameter': 'output',
     'description': "Moran's I spatial autocorrelation from a distance matrix."}

    def run(self, ctx: Context, inputs) -> None:
        value_form, weight_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_b_dim = ctx.step_params.get("sample_b_dim", "sample_b")
        value_label = ctx.step_params.get("value_label")
        weighting = ctx.step_params.get("weighting", "inverse")
        if weighting not in {"inverse", "binary"}:
            raise StepError("moran: weighting must be 'inverse' or 'binary'")

        samples, values = _single_column(value_form, sample_dim, feature_dim, value_label)
        distances, matrix_labels = distance(weight_form, sample_dim, sample_b_dim, "moran")
        if weight_form.dims.index(sample_dim) == 1:
            distances = distances.T
        if sorted(matrix_labels) != sorted(samples):
            raise StepError("moran: distance labels differ from value samples")
        position = {label: index for index, label in enumerate(matrix_labels)}
        order = [position[label] for label in samples]
        distances = distances[np.ix_(order, order)]

        if weighting == "inverse":
            weights = np.zeros_like(distances)
            positive = distances > 0.0
            weights[positive] = 1.0 / distances[positive]
        else:
            weights = (distances > 0.0).astype(np.float64)
        np.fill_diagonal(weights, 0.0)

        n = float(values.size)
        rows = weights.sum(axis=1)
        rows = np.where(rows == 0.0, 1.0, rows)
        weights = weights / rows[:, None]
        total = float(weights.sum())
        if total == 0.0:
            raise StepError("moran: weights sum to zero")
        centred = values - values.mean()
        spread = float(centred @ centred)
        if spread == 0.0:
            raise StepError("moran: values are constant")
        observed = (n / total) * float(centred @ weights @ centred) / spread
        expected = -1.0 / (n - 1.0)
        s1 = 0.5 * float(((weights + weights.T) ** 2).sum())
        s2 = float(((weights.sum(axis=1) + weights.sum(axis=0)) ** 2).sum())
        total_sq = total * total
        kurtosis = float((centred ** 4).sum() / n) / (spread / n) ** 2
        numerator = n * ((n * n - 3.0 * n + 3.0) * s1 - n * s2 + 3.0 * total_sq) - kurtosis * (
            n * (n - 1.0) * s1 - 2.0 * n * s2 + 6.0 * total_sq
        )
        variance = numerator / (
            (n - 1.0) * (n - 2.0) * (n - 3.0) * total_sq
        ) - 1.0 / ((n - 1.0) ** 2)
        sd = float(np.sqrt(variance)) if variance > 0.0 else float("nan")
        if np.isfinite(sd) and sd > 0.0:
            p_value = 2.0 * NormalDist().cdf(-abs(observed - expected) / sd)
        else:
            p_value = float("nan")

        out = scalar_form(
            [observed, expected, sd, p_value, n],
            ["observed", "expected", "sd", "p_value", "n_samples"],
            "moran",
        )
        out.info["weighting"] = weighting
        ctx[ctx.step_params.get("output", self.name)] = out
        self._export = {
            "observed": observed,
            "expected": expected,
            "sd": sd,
            "p_value": p_value,
            "n_samples": int(n),
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export", {})
