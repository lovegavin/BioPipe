"""Partitioning around medoids (PAM)."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import labels_in_order, reorder


def _build(medoids: list[int], distances: np.ndarray, n_clusters: int) -> None:
    while len(medoids) < n_clusters:
        nearest = distances[:, medoids].min(axis=1)
        gain = np.maximum(nearest[:, None] - distances, 0.0).sum(axis=0)
        gain[medoids] = -np.inf
        medoids.append(int(np.argmax(gain)))


def _swap(distances: np.ndarray, medoids: np.ndarray, max_iter: int) -> tuple[np.ndarray, int]:
    n = distances.shape[0]
    k = medoids.shape[0]
    iterations = 0
    while iterations < max_iter:
        nearest = distances[:, medoids].min(axis=1)
        old_cost = float(nearest.sum())
        best_delta = -1e-12
        best = None
        for position in range(k):
            others = np.delete(medoids, position)
            base = distances[:, others].min(axis=1) if others.size else np.full(n, np.inf)
            candidate = np.minimum(base[:, None], distances)
            candidate[others, :] = 0.0
            delta = candidate.sum(axis=0) - old_cost
            delta[medoids] = np.inf
            delta[medoids[position]] = np.inf
            index = int(np.argmin(delta))
            if delta[index] < best_delta:
                best_delta = float(delta[index])
                best = (position, index)
        if best is None:
            break
        medoids[best[0]] = best[1]
        iterations += 1
    return medoids, iterations


class PamStep(Step):
    provider = 'operon-core'
    parameters_file = 'pam.PamStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'pam',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Partitioning around medoids',
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
     'description': ('PAM（围绕中心点划分）：欧氏距离、BUILD 选取初始中心点，'
                     'SWAP 以精确代价下降迭代，输出每个样本的簇编号与到中心点距离。')}

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        n_clusters = int(ctx.step_params["n_clusters"])
        max_iter = int(ctx.step_params.get("max_iter", 100))
        out_name = ctx.step_params.get("output", self.name)
        matrix = np.asarray(reorder(form, sample_dim, feature_dim), dtype=np.float64)
        samples = labels_in_order(form, sample_dim)
        n = matrix.shape[0]
        if not np.isfinite(matrix).all():
            raise StepError("pam: input contains missing or infinite values")
        if n < 3:
            raise StepError("pam: at least three samples are required")
        if not 2 <= n_clusters < n:
            raise StepError(
                f"pam: n_clusters must satisfy 2 <= n_clusters < n_samples, got "
                f"{n_clusters} for {n} samples"
            )
        squared = np.sum((matrix[:, None, :] - matrix[None, :, :]) ** 2, axis=2)
        distances = np.sqrt(np.maximum(squared, 0.0))
        np.fill_diagonal(distances, 0.0)
        medoids = [int(np.argmin(distances.sum(axis=0)))]
        _build(medoids, distances, n_clusters)
        build_objective = float(distances[:, medoids].min(axis=1).mean())
        medoids_array, iterations = _swap(distances, np.asarray(medoids, dtype=int), max_iter)
        nearest = distances[:, medoids_array]
        clusters = np.argmin(nearest, axis=1) + 1
        best = np.min(nearest, axis=1)
        objective = float(best.mean())
        data = np.column_stack([clusters, best]).astype(np.float32)
        ctx[out_name] = Form(
            data=data,
            dims=[sample_dim, "statistic"],
            labels={sample_dim: {name: i for i, name in enumerate(samples)},
                    "statistic": {"cluster": 0, "distance": 1}},
            info={"missing_code": np.nan},
        )
        self._export_data = {
            "n_clusters": int(n_clusters),
            "n_samples": int(n),
            "medoids": [int(value) for value in medoids_array],
            "medoid_labels": [samples[int(value)] for value in medoids_array],
            "objective": objective,
            "build_objective": build_objective,
            "iterations": int(iterations),
            "total_distance": float(best.sum()),
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
