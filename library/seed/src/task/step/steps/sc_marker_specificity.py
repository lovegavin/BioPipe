"""Marker specificity (tau) per gene across single-cell clusters."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._sc_utils import axis_labels, group_ids, matrix2d

STATS = ["top_cluster", "specificity_tau", "max_mean", "max_detected_fraction", "overall_detected_fraction"]


class ScMarkerSpecificityStep(Step):
    """Rank genes by how specifically they mark one cluster."""

    provider = "operon-core"
    parameters_file = "sc_marker_specificity.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sc_marker_specificity",
        "version": "1.0.0",
        "kind": "operator",
        "title": "sc_marker_specificity",
        "description": "Tau specificity and detection rates of genes across clusters.",
        "category": "Omics",
        "icon": "Target",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "kind": ["form"],
                    "numeric": True,
                    "ndim": 2,
                    "dims": ["cell", "gene"],
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
                    "dims": ["gene", "statistic"],
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
        cells = genes = 0
        for item in inputs or []:
            data = getattr(item, "data", None)
            if data is not None and getattr(data, "ndim", 0) == 2:
                cells = max(cells, int(data.shape[0]))
                genes = max(genes, int(data.shape[1]))
        return max(cells * genes * 8, 8 * 1024**2), max(genes * 64, 512 * 1024)

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or len(inputs) != 2:
            raise StepError("sc_marker_specificity requires an expression matrix and clusters")
        expression, groups = inputs
        params = dict(ctx.step_params)
        cell_dim = str(params.get("cell_dim") or "cell")
        gene_dim = str(params.get("gene_dim") or "gene")
        cluster_dim = str(params.get("cluster_dim") or "cluster")
        min_cells = int(params.get("min_cells") or 3)
        out_name = params.get("output") or self.name

        matrix = matrix2d(expression, cell_dim, gene_dim, "sc_marker_specificity")
        genes = axis_labels(expression, gene_dim, matrix.shape[1], "sc_marker_specificity")
        clusters = group_ids(groups, matrix.shape[0], cell_dim, cluster_dim, "sc_marker_specificity")
        names = sorted(set(clusters), key=lambda value: (len(value), value))
        if len(names) < 2:
            raise StepError("sc_marker_specificity requires at least two clusters")

        cluster_array = np.asarray(clusters)
        means = np.zeros((len(names), matrix.shape[1]), dtype=float)
        fractions = np.zeros_like(means)
        keep: list[str] = []
        for row, name in enumerate(names):
            mask = cluster_array == name
            if int(mask.sum()) < min_cells:
                continue
            keep.append(name)
            block = matrix[mask]
            means[row] = block.mean(axis=0)
            fractions[row] = (block > 0).mean(axis=0)
        if len(keep) < 2:
            raise StepError("not enough clusters with the requested minimum number of cells")
        means = means[: len(keep)]
        fractions = fractions[: len(keep)]

        peaks = means.max(axis=0)
        safe = np.where(peaks > 0, peaks, 1.0)
        scaled = means / safe
        tau = np.sum(1.0 - scaled, axis=0) / (len(keep) - 1)
        tau = np.where(peaks > 0, tau, 0.0)
        top = means.argmax(axis=0)
        rows = []
        for index in range(matrix.shape[1]):
            rows.append(
                [
                    float(top[index]),
                    float(tau[index]),
                    float(peaks[index]),
                    float(fractions[top[index], index]),
                    float((matrix[:, index] > 0).mean()),
                ]
            )
        data = np.asarray(rows, dtype=float) if rows else np.zeros((0, len(STATS)))
        out = Form(
            data=data,
            dims=["gene", "statistic"],
            labels={
                "gene": {name: index for index, name in enumerate(genes)},
                "statistic": {name: index for index, name in enumerate(STATS)},
            },
            info={
                "clusters": keep,
                "n_clusters": len(keep),
                "n_genes": matrix.shape[1],
                "n_cells": matrix.shape[0],
                "min_cells": min_cells,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_clusters": len(keep),
            "n_genes": matrix.shape[1],
            "n_cells": matrix.shape[0],
            "max_tau": float(tau.max()) if tau.size else 0.0,
        }
        print(f"[sc_marker_specificity] clusters={len(keep)} genes={matrix.shape[1]}")

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
