"""Principal coordinates of neighbourhood matrices (PCNM)."""
from __future__ import annotations

import numpy as np
from scipy.sparse.csgraph import minimum_spanning_tree

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import distance


def _threshold(matrix: np.ndarray) -> float:
    """Largest edge of the minimum spanning tree, as ``vegan::spantree``."""
    n = matrix.shape[0]
    work = matrix.copy()
    off_diagonal = ~np.eye(n, dtype=bool)
    work[off_diagonal & (work == 0.0)] = 1e-12
    tree = minimum_spanning_tree(work)
    rows, cols = tree.nonzero()
    if rows.size == 0:
        raise StepError("pcnm: cannot build a spanning tree from the distance matrix")
    return float(np.max(work[rows, cols]))


class PcnmStep(Step):
    """Principal coordinates of a truncated distance matrix.

    The default threshold is the largest edge of the minimum spanning tree of
    the input distances; distances longer than the threshold are replaced by
    ``4 * threshold`` before classical multidimensional scaling, which is the
    convention used by ``vegan::pcnm``.
    """

    provider = 'operon-core'

    parameters_file = 'pcnm.PcnmStep.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'pcnm',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Principal coordinates of neighbourhood matrices',
     'category': 'Statistics',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
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
     'dependencies': ['numpy>=1.24', 'scipy>=1.11'],
     'dependency_imports': ['numpy', 'scipy'],
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output',
     'description': 'Classical MDS axes of a distance matrix truncated at the PCNM threshold.'}

    def run(self, ctx: Context, inputs) -> None:
        (distance_form,) = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        sample_b_dim = ctx.step_params.get("sample_b_dim", "sample_b")
        matrix, samples = distance(distance_form, sample_dim, sample_b_dim, "pcnm")
        n = matrix.shape[0]
        if n < 3:
            raise StepError("pcnm: need at least three samples")
        if not np.allclose(matrix, matrix.T, atol=1e-8) or np.any(np.abs(np.diag(matrix)) > 1e-8):
            raise StepError("pcnm: distance matrix must be symmetric with a zero diagonal")

        threshold = ctx.step_params.get("threshold")
        if threshold is None:
            threshold_value = _threshold(matrix)
        else:
            threshold_value = float(threshold)
            if not np.isfinite(threshold_value) or threshold_value <= 0.0:
                raise StepError("pcnm: threshold must be a positive finite number")

        truncated = np.where(matrix > threshold_value, 4.0 * threshold_value, matrix)
        centering = np.eye(n) - np.ones((n, n)) / n
        gram = -0.5 * centering @ (truncated ** 2) @ centering
        eigenvalues, eigenvectors = np.linalg.eigh(gram)
        order = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[order]
        eigenvectors = eigenvectors[:, order]
        scale = max(float(np.max(np.abs(eigenvalues))), 1.0)
        positive = np.flatnonzero(eigenvalues > 1e-12 * scale)
        if positive.size == 0:
            raise StepError("pcnm: the truncated distance matrix has no positive axes")
        n_axes = int(ctx.step_params.get("n_axes", 0) or 0)
        if n_axes > 0:
            positive = positive[:n_axes]
        axes = eigenvectors[:, positive]
        for column in range(axes.shape[1]):
            vector = axes[:, column]
            magnitude = float(np.max(np.abs(vector)))
            pivot = int(np.flatnonzero(np.abs(vector) >= magnitude * (1.0 - 1e-9))[0])
            if vector[pivot] < 0.0:
                axes[:, column] = -vector
        values = eigenvalues[positive]

        axis_labels = {f"PCNM{index + 1}": index for index in range(len(values))}
        out_name = ctx.step_params.get("output", self.name)
        ctx[out_name] = Form(
            data=np.asarray(axes, dtype=np.float32),
            dims=["sample", "axis"],
            labels={
                "sample": {name: index for index, name in enumerate(samples)},
                "axis": axis_labels,
            },
            info={
                "missing_code": np.nan,
                "method": "pcnm",
                "threshold": threshold_value,
                "eigenvalues": [float(value) for value in values],
            },
        )
        self._export_data = {
            "threshold": threshold_value,
            "n_axes": int(len(values)),
            "eigenvalues": [float(value) for value in values],
        }
        print(f"[pcnm] {len(values)} axes, threshold {threshold_value:.6g}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
