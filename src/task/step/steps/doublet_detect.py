# src/task/step/steps/doublet_detect.py
"""Per-cell doublet scores using Scanpy's Scrublet implementation.

Scrublet is the classic simulation-based doublet detector. The operator
wraps it directly, so the score and predicted-doublet threshold follow
the upstream implementation rather than a reimplementation.

Output is [cell, statistic] with columns doublet_score,
predicted_doublet and n_genes.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import axis_labels, labels_in_order, make_form, reorder, require_dims


class DoubletDetectStep(Step):
    name = "doublet_detect"
    title = "Doublet detection"
    category = "Single cell"
    builtin_package = "biopipe-core"
    dependencies = ["scanpy>=1.10", "anndata>=0.10"]
    dependency_imports = ["scanpy", "anndata"]
    inputs_arity = 1
    outputs = []
    input_contracts = [port(ndim=2, dims=[param("cell_dim", "cell"), param("gene_dim", "gene")])]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
        "info": {"missing_code": {"type": ["number", "null"]}}}}
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "cell_dim": {"type": "string", "default": "cell"},
            "gene_dim": {"type": "string", "default": "gene"},
            "expected_doublet_rate": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.06},
            "random_state": {"type": "integer", "default": 0},
            "threshold": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.25},
            "n_prin_comps": {"type": "integer", "minimum": 2, "default": 20},
            "output": {"type": "string"},
        },
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        cell_dim = ctx.step_params.get("cell_dim", "cell")
        gene_dim = ctx.step_params.get("gene_dim", "gene")
        rate = float(ctx.step_params.get("expected_doublet_rate", 0.06))
        seed = int(ctx.step_params.get("random_state", 0))
        threshold = float(ctx.step_params.get("threshold", 0.25))
        n_prin_comps = int(ctx.step_params.get("n_prin_comps", 20))
        out_name = ctx.step_params.get("output", self.name)
        require_dims(form, cell_dim, gene_dim, label="counts")
        try:
            import anndata as ad
            import scanpy as sc
        except ImportError as exc:
            raise StepError("doublet_detect requires anndata and scanpy") from exc
        data = reorder(form, cell_dim, gene_dim)
        cells = labels_in_order(form, cell_dim)
        genes = labels_in_order(form, gene_dim)
        adata = ad.AnnData(X=np.asarray(data, dtype=np.float32))
        adata.obs_names = cells
        adata.var_names = genes
        sc.pp.scrublet(adata, expected_doublet_rate=rate, random_state=seed, threshold=threshold, n_prin_comps=n_prin_comps)
        scores = np.asarray(adata.obs["doublet_score"], dtype=np.float64)
        predicted = np.asarray(adata.obs["predicted_doublet"], dtype=bool)
        n_genes = np.asarray([np.count_nonzero(row) for row in data], dtype=np.float64)
        out = np.column_stack([scores, predicted.astype(np.float64), n_genes])
        result = make_form(
            out, [cell_dim, "statistic"],
            {cell_dim: axis_labels(cells, cell_dim),
             "statistic": {"doublet_score": 0, "predicted_doublet": 1, "n_genes": 2}},
        )
        ctx[out_name] = result
        self._export_data = {
            "n_cells": len(cells), "n_predicted": int(predicted.sum()),
            "expected_doublet_rate": rate, "random_state": seed,
            "threshold": threshold, "n_prin_comps": n_prin_comps,
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "n_cells": len(cells), "n_predicted": int(predicted.sum()),
        }

    def export(self, ctx: Context) -> dict:
        return self._export_data
