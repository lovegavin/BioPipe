"""Gene expression trends along a pseudotime axis.

Inputs: a 2D expression matrix [cell, gene] and 2D pseudotime [cell, pseudotime].
Output: 2D Form [gene, bin] with the mean expression in each pseudotime bin.
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


def _pseudotime_vector(form: Form, n: int) -> np.ndarray:
    data = np.asarray(form.data, dtype=float)
    if data.ndim == 2:
        if data.shape[1] != 1:
            raise ValueError("pseudotime must have exactly one column")
        data = data[:, 0]
    if data.ndim != 1 or data.size != n:
        raise ValueError("one pseudotime value per cell is required")
    if not np.all(np.isfinite(data)):
        raise ValueError("pseudotime contains non-finite values")
    return data


def gene_trends(expression, pseudotime, n_bins: int = 10):
    x = np.asarray(expression, dtype=float)
    if x.ndim != 2:
        raise ValueError("expression must be 2D")
    if x.shape[0] != pseudotime.size:
        raise ValueError("expression and pseudotime disagree on the number of cells")
    n_bins = max(1, int(n_bins))
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bins = np.digitize(pseudotime, edges[1:-1], right=False)
    bins = np.clip(bins, 0, n_bins - 1)

    trends = np.full((x.shape[1], n_bins), np.nan, dtype=float)
    for index in range(n_bins):
        mask = bins == index
        if np.any(mask):
            trends[:, index] = x[mask].mean(axis=0)
    return trends


class TrajectoryGeneTrendsStep(Step):
    """Mean gene expression in equal-width pseudotime bins."""

    provider = "operon-core"
    parameters_file = "trajectory_gene_trends.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "trajectory_gene_trends",
        "version": "1.0.0",
        "kind": "operator",
        "title": "trajectory_gene_trends",
        "description": "Mean gene expression across equal-width pseudotime bins.",
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
                    "dims": ["cell", "pseudotime"],
                },
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "kind": "form",
                    "numeric": True,
                    "ndim": 2,
                    "dims": ["gene", "bin"],
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
        if inputs:
            data = getattr(inputs[0], "data", None)
            if data is not None and getattr(data, "ndim", 0) == 2:
                cells, genes = int(data.shape[0]), int(data.shape[1])
        return max(cells * genes * 8, 8 * 1024**2), max(genes * 8, 1024)

    def run(self, ctx: Context, inputs) -> None:
        if not inputs or len(inputs) != 2:
            raise StepError("trajectory_gene_trends requires expression and pseudotime")
        expression, pseudotime_form = inputs
        if not isinstance(expression, Form) or not isinstance(pseudotime_form, Form):
            raise StepError("trajectory_gene_trends requires two Forms")
        if expression.data.ndim != 2:
            raise StepError("trajectory_gene_trends requires a 2D expression matrix")
        params = dict(ctx.step_params)
        n_bins = int(params.get("n_bins") or 10)
        out_name = params.get("output") or self.name
        genes = _axis_labels(expression, "gene", expression.data.shape[1])
        try:
            pseudotime = _pseudotime_vector(pseudotime_form, expression.data.shape[0])
            trends = gene_trends(expression.data, pseudotime, n_bins)
        except ValueError as exc:
            raise StepError(f"trajectory_gene_trends: {exc}") from exc

        labels = {
            "gene": {gene: index for index, gene in enumerate(genes)},
            "bin": {str(index): index for index in range(n_bins)},
        }
        info = {"n_bins": n_bins, "n_cells": int(expression.data.shape[0])}
        ctx[out_name] = Form(
            data=trends,
            dims=["gene", "bin"],
            labels=labels,
            info=info,
        )
        covered = int(np.count_nonzero(~np.isnan(trends).all(axis=0)))
        self._export_data = {
            "n_genes": len(genes),
            "n_bins": n_bins,
            "n_occupied_bins": covered,
        }
        print(f"[trajectory_gene_trends] genes={len(genes)} bins={n_bins}")

    def export(self, ctx):
        return self._export_data
