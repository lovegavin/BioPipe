"""Per-cluster expression and detection profile."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._sc_utils import axis_labels, group_ids, matrix2d

STATS = ["mean", "detected_fraction", "n_cells"]


class ScClusterProfileStep(Step):
    """Mean expression and detection fraction for every cluster and gene."""

    provider = "operon-core"
    parameters_file = "sc_cluster_profile.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sc_cluster_profile",
        "version": "1.0.0",
        "kind": "operator",
        "title": "sc_cluster_profile",
        "description": "Per-cluster mean expression and detection fraction.",
        "category": "Omics",
        "icon": "Grid",
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
                    "dims": ["cluster_gene", "statistic"],
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
            raise StepError("sc_cluster_profile requires an expression matrix and clusters")
        expression, groups = inputs
        params = dict(ctx.step_params)
        cell_dim = str(params.get("cell_dim") or "cell")
        gene_dim = str(params.get("gene_dim") or "gene")
        cluster_dim = str(params.get("cluster_dim") or "cluster")
        min_cells = int(params.get("min_cells") or 1)
        out_name = params.get("output") or self.name

        matrix = matrix2d(expression, cell_dim, gene_dim, "sc_cluster_profile")
        genes = axis_labels(expression, gene_dim, matrix.shape[1], "sc_cluster_profile")
        clusters = group_ids(groups, matrix.shape[0], cell_dim, cluster_dim, "sc_cluster_profile")
        names = sorted(set(clusters), key=lambda value: (len(value), value))
        cluster_array = np.asarray(clusters)

        rows = []
        labels: dict[str, int] = {}
        kept = []
        for name in names:
            mask = cluster_array == name
            count = int(mask.sum())
            if count < min_cells:
                continue
            kept.append(name)
            block = matrix[mask]
            mean = block.mean(axis=0)
            detected = (block > 0).mean(axis=0)
            for index in range(matrix.shape[1]):
                label = f"{name}|{genes[index]}"
                labels[label] = len(labels)
                rows.append([float(mean[index]), float(detected[index]), float(count)])
        if not kept:
            raise StepError("no cluster passed the minimum cell count")

        data = np.asarray(rows, dtype=float) if rows else np.zeros((0, len(STATS)))
        out = Form(
            data=data,
            dims=["cluster_gene", "statistic"],
            labels={
                "cluster_gene": labels,
                "statistic": {name: index for index, name in enumerate(STATS)},
            },
            info={
                "clusters": kept,
                "n_clusters": len(kept),
                "n_genes": matrix.shape[1],
                "n_cells": matrix.shape[0],
                "min_cells": min_cells,
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_clusters": len(kept),
            "n_genes": matrix.shape[1],
            "n_cells": matrix.shape[0],
            "n_rows": len(labels),
        }
        print(f"[sc_cluster_profile] clusters={len(kept)} genes={matrix.shape[1]} rows={len(labels)}")

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
