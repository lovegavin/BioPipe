"""Diffusion pseudotime over a low-dimensional embedding.

Input: 2D numeric Form [cell, component] (for example PCA scores).
Output: 2D Form [cell, pseudotime] with one column in [0, 1].

The implementation builds an adaptive Gaussian kNN graph, symmetrises it and
uses the leading diffusion components of the random-walk matrix, weighted by
lambda / (1 - lambda) as in Haghverdi et al. (2016), Eq. 15. Pseudotime is the
Euclidean distance to the root cell in that diffusion space, normalised by its
maximum.
"""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


def _axis_labels(form: Form, dim: str, n: int):
    labels = (form.labels or {}).get(dim)
    if labels:
        return list(labels.keys())
    return [str(i) for i in range(n)]


def diffusion_pseudotime(embedding, root_index: int, n_neighbors: int = 15, n_dcs: int = 10):
    x = np.asarray(embedding, dtype=float)
    if x.ndim != 2 or x.shape[0] < 3:
        raise ValueError("embedding must be a 2D matrix with at least three rows")
    n = x.shape[0]
    k = max(1, min(int(n_neighbors), n - 1))
    n_dcs = max(1, min(int(n_dcs), n - 2))

    sq = np.einsum("ij,ij->i", x, x)
    d2 = sq[:, None] + sq[None, :] - 2.0 * (x @ x.T)
    np.maximum(d2, 0.0, out=d2)
    dist = np.sqrt(d2)
    np.fill_diagonal(dist, np.inf)
    order = np.argsort(dist, axis=1)[:, :k]
    dk = np.take_along_axis(dist, order, axis=1)
    sigma = dk[:, -1].copy()
    sigma[sigma <= 0.0] = np.finfo(float).eps

    rows = np.repeat(np.arange(n), k)
    cols = order.ravel()
    values = np.exp(-(dist[rows, cols] ** 2) / (sigma[rows] * sigma[cols]))
    kernel = np.zeros((n, n), dtype=float)
    kernel[rows, cols] = values
    kernel = np.maximum(kernel, kernel.T)

    degree = kernel.sum(axis=1)
    degree[degree <= 0.0] = 1.0
    inv_sqrt = 1.0 / np.sqrt(degree)
    symmetric = kernel * inv_sqrt[:, None] * inv_sqrt[None, :]

    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
    eigenvalues = eigenvalues[::-1][1 : n_dcs + 1]
    eigenvectors = eigenvectors[:, ::-1][:, 1 : n_dcs + 1]
    eigenvalues = np.where(np.abs(eigenvalues) < 1e-12, 1e-12, eigenvalues)

    psi = eigenvectors * inv_sqrt[:, None]
    # Haghverdi et al. (2016), Eq. 15: weight component j by lambda_j / (1 - lambda_j).
    weights = eigenvalues / np.maximum(1.0 - eigenvalues, 1e-12)
    scaled = psi * weights[None, :]
    delta = scaled - scaled[root_index]
    dpt = np.sqrt(np.einsum("ij,ij->i", delta, delta))
    peak = float(dpt.max())
    if peak > 0.0:
        dpt = dpt / peak
    return dpt


class PseudotimeDptStep(Step):
    """Diffusion pseudotime from a cell-by-component embedding."""

    provider = "operon-core"
    parameters_file = "pseudotime_dpt.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "pseudotime_dpt",
        "version": "1.0.0",
        "kind": "operator",
        "title": "pseudotime_dpt",
        "description": "Diffusion pseudotime over a low-dimensional cell embedding.",
        "category": "Omics",
        "icon": "Route",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "kind": ["form"],
                    "numeric": True,
                    "ndim": 2,
                    "dims": ["cell", "component"],
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "kind": "form",
                    "numeric": True,
                    "ndim": 2,
                    "dims": ["cell", "pseudotime"],
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        n = 0
        for item in inputs or []:
            data = getattr(item, "data", None)
            if data is not None and getattr(data, "ndim", 0) == 2:
                n = max(n, int(data.shape[0]))
        return max(n * n * 8 * 4, 8 * 1024**2), max(n * 8, 1024)

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or not isinstance(inputs[0], Form):
            raise StepError("pseudotime_dpt requires a 2D embedding Form")
        form = inputs[0]
        if form.data.ndim != 2:
            raise StepError(f"pseudotime_dpt requires a 2D embedding, got {form.data.ndim}D")
        params = dict(ctx.step_params)
        n_neighbors = int(params.get("n_neighbors") or 15)
        n_dcs = int(params.get("n_dcs") or 10)
        out_name = params.get("output") or self.name
        cells = _axis_labels(form, "cell", form.data.shape[0])
        root = str(params.get("root_cell") or "")
        if root:
            if root not in cells:
                raise StepError(f"pseudotime_dpt: root cell {root!r} is not in the embedding")
            root_index = cells.index(root)
        else:
            root_index = 0

        try:
            dpt = diffusion_pseudotime(form.data, root_index, n_neighbors, n_dcs)
        except ValueError as exc:
            raise StepError(f"pseudotime_dpt: {exc}") from exc

        labels = {
            "cell": {cell: index for index, cell in enumerate(cells)},
            "pseudotime": {"pseudotime": 0},
        }
        info = {
            "root_cell": cells[root_index],
            "n_neighbors": int(n_neighbors),
            "n_dcs": int(n_dcs),
        }
        ctx[out_name] = Form(
            data=dpt.reshape(-1, 1),
            dims=["cell", "pseudotime"],
            labels=labels,
            info=info,
        )
        self._export_data = {
            "n_cells": int(dpt.size),
            "root_cell": cells[root_index],
            "pseudotime_min": float(dpt.min()),
            "pseudotime_max": float(dpt.max()),
        }
        print(
            f"[pseudotime_dpt] cells={dpt.size} root={cells[root_index]} "
            f"range={dpt.min():.4f}..{dpt.max():.4f}"
        )

    def export(self, ctx):
        return self._export_data
