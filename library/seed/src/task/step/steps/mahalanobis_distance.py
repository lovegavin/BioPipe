"""Squared Mahalanobis distance for each sample."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame


class MahalanobisDistanceStep(Step):
    provider = 'operon-core'
    """Squared Mahalanobis distance from the sample mean.

    The covariance is the sample covariance with ``ddof=1``; distances are
    compared to a chi-square distribution with ``p`` degrees of freedom.
    """
    parameters_file = 'mahalanobis_distance.MahalanobisDistanceStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'mahalanobis_distance',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Mahalanobis distance',
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
                                         'axis_info_open': True}}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'dependencies': ['numpy>=1.24', 'scipy>=1.11'],
     'dependency_imports': ['numpy', 'scipy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Squared Mahalanobis distance from the sample mean.'}


    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        out_name = ctx.step_params.get("output", self.name)
        frame = table_frame(form, sample_dim, feature_dim, "mahalanobis_distance")
        features = [name for name in frame.columns if name != "__sample__"]
        if not features:
            raise StepError("mahalanobis_distance: no feature columns")
        matrix = np.column_stack([
            np.asarray(numeric_column(frame, name, "mahalanobis_distance"), dtype=np.float64)
            for name in features
        ])
        if not np.isfinite(matrix).all():
            raise StepError("mahalanobis_distance: require complete numeric rows")
        n, p = matrix.shape
        if n <= p:
            raise StepError("mahalanobis_distance: need more samples than features")
        covariance = np.cov(matrix, rowvar=False, ddof=1)
        if covariance.ndim == 0:
            covariance = np.asarray([[float(covariance)]])
        if np.linalg.matrix_rank(covariance) < p:
            raise StepError("mahalanobis_distance: covariance matrix is singular")
        center = matrix.mean(axis=0)
        diff = matrix - center
        distances = np.einsum("ij,jk,ik->i", diff, np.linalg.inv(covariance), diff)
        distances = np.maximum(distances, 0.0)
        p_values = stats.chi2.sf(distances, p)
        samples = [name for name, _ in sorted(form.labels[sample_dim].items(), key=lambda item: item[1])]

        out = Form(
            data=np.column_stack([distances, p_values]).astype(np.float32),
            dims=[sample_dim, "statistic"],
            labels={
                sample_dim: {name: i for i, name in enumerate(samples)},
                "statistic": {"distance": 0, "p": 1},
            },
            info={"missing_code": np.nan, "method": "squared Mahalanobis distance"},
        )
        ctx[out_name] = out
        self._export_data = {
            "n_samples": n, "n_features": p, "center": center.tolist(),
            "mean_distance": float(distances.mean()),
            "max_distance": float(distances.max()),
            "min_p": float(p_values.min()),
        }
        print(f"[mahalanobis_distance] {n} samples, {p} features")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
