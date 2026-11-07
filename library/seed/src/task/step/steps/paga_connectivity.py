"""PAGA-style cluster connectivity from a cell embedding.

Inputs: a 2D embedding [cell, component] and a 2D label matrix [cell, cluster].
Output: a symmetric 2D Form [cluster, cluster_b] with connectivity in [0, 1].

Connectivity is the number of kNN edges between two clusters divided by the
product of their sizes, then scaled so the strongest off-diagonal link is 1.
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


def _cluster_ids(labels_form: Form, n: int):
    data = np.asarray(labels_form.data)
    if data.ndim == 2:
        if data.shape[1] != 1:
            raise ValueError("cluster labels must have exactly one column")
        data = data[:, 0]
    if data.ndim != 1 or data.size != n:
        raise ValueError("cluster labels must have one value per cell")
    ids = []
    for value in data:
        number = float(value)
        ids.append(str(int(round(number))) if number.is_integer() else f"{number:g}")
    return ids


def paga_connectivity(embedding, cluster_ids, n_neighbors: int = 15) -> np.ndarray:
    x = np.asarray(embedding, dtype=float)
    if x.ndim != 2:
        raise ValueError("embedding must be 2D")
    n = x.shape[0]
    if len(cluster_ids) != n:
        raise ValueError("one cluster label per cell is required")
    k = max(1, min(int(n_neighbors), n - 1))

    sq = np.einsum("ij,ij->i", x, x)
    d2 = sq[:, None] + sq[None, :] - 2.0 * (x @ x.T)
    np.maximum(d2, 0.0, out=d2)
    dist = np.sqrt(d2)
    np.fill_diagonal(dist, np.inf)
    order = np.argsort(dist, axis=1)[:, :k]

    names = sorted(set(cluster_ids))
    index = {name: position for position, name in enumerate(names)}
    sizes = np.zeros(len(names), dtype=float)
    for name in cluster_ids:
        sizes[index[name]] += 1.0
    counts = np.zeros((len(names), len(names)), dtype=float)
    for cell in range(n):
        a = index[cluster_ids[cell]]
        for neighbour in order[cell]:
            b = index[cluster_ids[int(neighbour)]]
            if a != b:
                counts[a, b] += 1.0
                counts[b, a] += 1.0

    connectivity = np.zeros_like(counts)
    for a in range(len(names)):
        for b in range(len(names)):
            if a != b:
                connectivity[a, b] = counts[a, b] / (sizes[a] * sizes[b])
    peak = float(connectivity.max()) if connectivity.size else 0.0
    if peak > 0.0:
        connectivity = connectivity / peak
    return names, connectivity


class PagaConnectivityStep(Step):
    """Cluster connectivity graph for a cell embedding."""

    provider = "operon-core"
    parameters_file = "paga_connectivity.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "paga_connectivity",
        "version": "1.0.0",
        "kind": "operator",
        "title": "paga_connectivity",
        "description": "PAGA-style connectivity between clusters on a cell embedding.",
        "category": "Omics",
        "icon": "Share2",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "kind": ["form"],
                    "numeric": True,
                    "ndim": 2,
                    "dims": ["cell", "component"],
                },
                {
                    "kind": ["form"],
                    "numeric": True,
                    "ndim": 2,
                    "dims": ["cell", "cluster"],
                },
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "kind": "form",
                    "numeric": True,
                    "ndim": 2,
                    "dims": ["cluster", "cluster_b"],
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
        "inputs_arity": 2,
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
        return max(n * n * 8 * 2, 8 * 1024**2), max(n * 8, 1024)

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or len(inputs) != 2:
            raise StepError("paga_connectivity requires an embedding and cluster labels")
        embedding, labels_form = inputs
        if not isinstance(embedding, Form) or not isinstance(labels_form, Form):
            raise StepError("paga_connectivity requires two Forms")
        if embedding.data.ndim != 2:
            raise StepError("paga_connectivity requires a 2D embedding")
        params = dict(ctx.step_params)
        n_neighbors = int(params.get("n_neighbors") or 15)
        out_name = params.get("output") or self.name
        cells = _axis_labels(embedding, "cell", embedding.data.shape[0])
        try:
            clusters = _cluster_ids(labels_form, embedding.data.shape[0])
            names, connectivity = paga_connectivity(embedding.data, clusters, n_neighbors)
        except ValueError as exc:
            raise StepError(f"paga_connectivity: {exc}") from exc

        labels = {
            "cluster": {name: index for index, name in enumerate(names)},
            "cluster_b": {name: index for index, name in enumerate(names)},
        }
        info = {"n_neighbors": int(n_neighbors), "n_clusters": len(names)}
        ctx[out_name] = Form(
            data=connectivity,
            dims=["cluster", "cluster_b"],
            labels=labels,
            info=info,
        )
        off = connectivity[~np.eye(len(names), dtype=bool)]
        self._export_data = {
            "n_clusters": len(names),
            "n_cells": len(cells),
            "max_connectivity": float(off.max()) if off.size else 0.0,
            "mean_connectivity": float(off.mean()) if off.size else 0.0,
        }
        print(f"[paga_connectivity] clusters={len(names)} cells={len(cells)}")

    def export(self, ctx):
        return self._export_data
