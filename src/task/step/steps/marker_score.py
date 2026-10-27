# src/task/step/steps/marker_score.py
"""Per-cell signature scores using Scanpy's score_genes.

The input gene sets are a binary [gene, gene_set] matrix, normally
produced by GmtReader. For every set Scanpy's control-gene-corrected
score is computed; genes absent from the expression matrix are skipped
and reported. This is the standard scanpy/Seurat-style signature score,
not a proprietary marker ranking.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import axis_labels, labels_in_order, make_form, reorder, require_dims


class MarkerScoreStep(Step):
    name = "marker_score"
    title = "Signature score"
    category = "Single cell"
    builtin_package = "biopipe-core"
    dependencies = ["scanpy>=1.10", "anndata>=0.10"]
    dependency_imports = ["scanpy", "anndata"]
    inputs_arity = 2
    outputs = []
    input_contracts = [
        port(ndim=2, dims=[param("cell_dim", "cell"), param("gene_dim", "gene")]),
        port(ndim=2, dims=[param("gene_dim", "gene"), param("gene_set_dim", "gene_set")]),
    ]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
        "info": {"missing_code": {"type": ["number", "null"]}}}}
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "cell_dim": {"type": "string", "default": "cell"},
            "gene_dim": {"type": "string", "default": "gene"},
            "gene_set_dim": {"type": "string", "default": "gene_set"},
            "min_genes": {"type": "integer", "minimum": 1, "default": 1},
            "ctrl_size": {"type": "integer", "minimum": 1, "default": 50},
            "n_bins": {"type": "integer", "minimum": 1, "default": 25},
            "random_state": {"type": "integer", "default": 0},
            "output": {"type": "string"},
        },
    }

    def run(self, ctx: Context, inputs) -> None:
        expr, sets = inputs
        cell_dim = ctx.step_params.get("cell_dim", "cell")
        gene_dim = ctx.step_params.get("gene_dim", "gene")
        set_dim = ctx.step_params.get("gene_set_dim", "gene_set")
        min_genes = int(ctx.step_params.get("min_genes", 1))
        ctrl_size = int(ctx.step_params.get("ctrl_size", 50))
        n_bins = int(ctx.step_params.get("n_bins", 25))
        seed = int(ctx.step_params.get("random_state", 0))
        out_name = ctx.step_params.get("output", self.name)
        require_dims(expr, cell_dim, gene_dim, label="expression")
        require_dims(sets, gene_dim, set_dim, label="gene sets")
        try:
            import anndata as ad
            import scanpy as sc
        except ImportError as exc:
            raise StepError("marker_score requires anndata and scanpy") from exc
        data = reorder(expr, cell_dim, gene_dim)
        cells = labels_in_order(expr, cell_dim)
        genes = labels_in_order(expr, gene_dim)
        adata = ad.AnnData(X=np.asarray(data, dtype=np.float32))
        adata.obs_names = cells
        adata.var_names = genes
        set_data = reorder(sets, gene_dim, set_dim)
        set_genes = labels_in_order(sets, gene_dim)
        set_names = labels_in_order(sets, set_dim)
        pos = {gene: i for i, gene in enumerate(set_genes)}
        scores = []
        kept = []
        skipped = {}
        for j, name in enumerate(set_names):
            members = [g for g in genes if pos.get(g) is not None and set_data[pos[g], j] > 0]
            if len(members) < min_genes:
                skipped[name] = len(members)
                continue
            column = f"__score_{len(kept)}"
            sc.tl.score_genes(
                adata, members, ctrl_size=ctrl_size, n_bins=n_bins,
                random_state=seed, score_name=column,
            )
            scores.append(np.asarray(adata.obs[column], dtype=np.float64))
            kept.append(name)
        if not kept:
            raise StepError(f"marker_score: no gene set has at least {min_genes} measured genes")
        out = np.column_stack(scores)
        form = make_form(
            out, [cell_dim, set_dim],
            {cell_dim: axis_labels(cells, cell_dim),
             set_dim: axis_labels(kept, set_dim)},
        )
        ctx[out_name] = form
        self._export_data = {
            "n_cells": len(cells), "sets_scored": kept,
            "sets_skipped": skipped, "min_genes": min_genes,
            "ctrl_size": ctrl_size, "n_bins": n_bins,
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "n_cells": len(cells), "sets_scored": len(kept),
        }

    def export(self, ctx: Context) -> dict:
        return self._export_data
