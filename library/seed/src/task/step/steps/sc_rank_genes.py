"""Per-cluster Wilcoxon rank-sum differential expression for single-cell data."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

from ._sc_utils import (
    axis_labels,
    bh_adjust,
    group_ids,
    log2_fold_change,
    matrix2d,
    wilcoxon_rank_sum,
)

STATS = [
    "log2fc",
    "mean_in",
    "mean_out",
    "pct_in",
    "pct_out",
    "p_value",
    "adjusted_p",
    "rank",
]


class ScRankGenesStep(Step):
    """Rank genes per cluster with a Wilcoxon rank-sum test."""

    provider = "operon-core"
    parameters_file = "sc_rank_genes.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "sc_rank_genes",
        "version": "1.0.0",
        "kind": "operator",
        "title": "sc_rank_genes",
        "description": "Cluster-versus-rest Wilcoxon differential expression for single-cell matrices.",
        "category": "Omics",
        "icon": "TrendingUp",
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
                    "dims": ["test", "statistic"],
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
        return max(cells * genes * 8, 16 * 1024**2), max(genes * 128, 1024 * 1024)

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or len(inputs) != 2:
            raise StepError("sc_rank_genes requires an expression matrix and cluster labels")
        expression, groups = inputs
        if not isinstance(expression, Form) or not isinstance(groups, Form):
            raise StepError("sc_rank_genes requires two Forms")
        params = dict(ctx.step_params)
        cell_dim = str(params.get("cell_dim") or "cell")
        gene_dim = str(params.get("gene_dim") or "gene")
        cluster_dim = str(params.get("cluster_dim") or "cluster")
        min_cells = int(params.get("min_cells") or 3)
        top_n = int(params.get("top_n") or 50)
        out_name = params.get("output") or self.name

        matrix = matrix2d(expression, cell_dim, gene_dim, "sc_rank_genes")
        genes = axis_labels(expression, gene_dim, matrix.shape[1], "sc_rank_genes")
        clusters = group_ids(groups, matrix.shape[0], cell_dim, cluster_dim, "sc_rank_genes")
        names = sorted(set(clusters), key=lambda value: (len(value), value))
        if len(names) < 2:
            raise StepError("sc_rank_genes requires at least two clusters")
        if top_n < 1:
            raise StepError("top_n must be positive")
        if min_cells < 2:
            raise StepError("min_cells must be at least 2")

        cluster_array = np.asarray(clusters)
        rows: list[list[float]] = []
        labels: dict[str, int] = {}
        for name in names:
            inside_mask = cluster_array == name
            n_in = int(inside_mask.sum())
            n_out = matrix.shape[0] - n_in
            if n_in < min_cells or n_out < min_cells:
                continue
            inside = matrix[inside_mask]
            outside = matrix[~inside_mask]
            p_values = np.empty(matrix.shape[1], dtype=float)
            log_fc = np.empty(matrix.shape[1], dtype=float)
            mean_in = inside.mean(axis=0)
            mean_out = outside.mean(axis=0)
            pct_in = (inside > 0).mean(axis=0)
            pct_out = (outside > 0).mean(axis=0)
            for index in range(matrix.shape[1]):
                _, _, p_value = wilcoxon_rank_sum(inside[:, index], outside[:, index])
                p_values[index] = p_value
                log_fc[index] = log2_fold_change(inside[:, index], outside[:, index])
            adjusted = bh_adjust(p_values)
            order = sorted(
                range(matrix.shape[1]),
                key=lambda index: (p_values[index], -log_fc[index], genes[index]),
            )
            for rank, index in enumerate(order[:top_n], start=1):
                label = f"{name}|{genes[index]}"
                labels[label] = len(labels)
                rows.append(
                    [
                        float(log_fc[index]),
                        float(mean_in[index]),
                        float(mean_out[index]),
                        float(pct_in[index]),
                        float(pct_out[index]),
                        float(p_values[index]),
                        float(adjusted[index]),
                        float(rank),
                    ]
                )

        data = np.asarray(rows, dtype=float) if rows else np.zeros((0, len(STATS)))
        out = Form(
            data=data,
            dims=["test", "statistic"],
            labels={
                "test": labels,
                "statistic": {name: index for index, name in enumerate(STATS)},
            },
            info={
                "n_clusters": len(names),
                "n_genes": matrix.shape[1],
                "n_cells": matrix.shape[0],
                "n_tests": len(labels),
                "top_n": top_n,
                "min_cells": min_cells,
                "test": "wilcoxon_rank_sum",
            },
        )
        out.validate()
        ctx[out_name] = out
        self._export_data = {
            "n_clusters": len(names),
            "n_genes": matrix.shape[1],
            "n_cells": matrix.shape[0],
            "n_tests": len(labels),
        }
        print(
            f"[sc_rank_genes] clusters={len(names)} genes={matrix.shape[1]} tests={len(labels)}"
        )

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
