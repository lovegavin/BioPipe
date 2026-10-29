# src/task/step/steps/ssgsea.py
"""Single-sample Gene Set Enrichment Analysis (ssGSEA).

This follows the rank-based statistic used by GSVA's ``ssgsea`` method:
for each sample, genes are ranked, a weighted rank-sum is compared with
the expected rank-sum outside the set, and scores are normalized by the
global range. It is a per-sample score, not the sample-level GSEA null.

The implementation is independent of GSVA. ``tests/test_r_oracles.py``
compares it with ``GSVA::gsva(ssgseaParam(...))`` when R/GSVA is present.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import axis_labels, labels_in_order, make_form, reorder, require_dims


class SsgseaStep(Step):
    name = "ssgsea"
    title = "ssGSEA"
    category = "Analysis"
    builtin_package = "biopipe-expression"
    inputs_arity = 2
    outputs = []
    input_contracts = [
        port(ndim=2, dims=[param("feature_dim", "feature"), param("sample_dim", "sample")]),
        port(ndim=2, dims=[param("gene_dim", "gene"), param("gene_set_dim", "gene_set")]),
    ]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
        "info": {"missing_code": {"type": ["number", "null"]}}}}
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "sample_dim": {"type": "string", "default": "sample"},
            "gene_dim": {"type": "string", "default": "gene"},
            "gene_set_dim": {"type": "string", "default": "gene_set"},
            "alpha": {"type": "number", "minimum": 0.0, "default": 0.25},
            "min_size": {"type": "integer", "minimum": 1, "default": 1},
            "normalize": {"type": "boolean", "default": True},
            "output": {"type": "string"},
        },
    }

    def run(self, ctx: Context, inputs) -> None:
        expr, sets = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        gene_dim = ctx.step_params.get("gene_dim", "gene")
        set_dim = ctx.step_params.get("gene_set_dim", "gene_set")
        alpha = float(ctx.step_params.get("alpha", 0.25))
        min_size = int(ctx.step_params.get("min_size", 1))
        normalize = bool(ctx.step_params.get("normalize", True))
        out_name = ctx.step_params.get("output", self.name)
        require_dims(expr, feature_dim, sample_dim, label="expression")
        require_dims(sets, gene_dim, set_dim, label="gene sets")
        if alpha < 0:
            raise StepError("ssgsea: alpha must be >= 0")
        data = reorder(expr, feature_dim, sample_dim)
        samples = labels_in_order(expr, sample_dim)
        genes = labels_in_order(expr, feature_dim)
        if not np.isfinite(data).all():
            raise StepError("ssgsea: expression matrix contains non-finite values")
        set_data = reorder(sets, gene_dim, set_dim)
        set_genes = labels_in_order(sets, gene_dim)
        set_names = labels_in_order(sets, set_dim)
        pos = {gene: i for i, gene in enumerate(set_genes)}
        members: list[list[int]] = []
        kept: list[str] = []
        skipped: dict[str, int] = {}
        for j, name in enumerate(set_names):
            idx = [i for i, gene in enumerate(genes)
                   if pos.get(gene) is not None and set_data[pos[gene], j] > 0]
            if len(idx) < min_size:
                skipped[name] = len(idx)
                continue
            if len(idx) >= len(genes):
                skipped[name] = len(idx)
                continue
            members.append(idx)
            kept.append(name)
        if not kept:
            raise StepError(f"ssgsea: no gene set has at least {min_size} measured genes")

        # R's colRanks(..., ties.method="average") followed by mode(R) <- "integer".
        # Average ranks that are not integral are truncated, matching that coercion.
        from scipy.stats import rankdata
        ranks = rankdata(data, axis=0, method="average").astype(np.int64)
        ra = np.abs(ranks.astype(np.float64)) ** alpha
        n = len(genes)
        scores = np.zeros((len(kept), len(samples)), dtype=np.float64)
        for j in range(len(samples)):
            ranking = np.argsort(-ranks[:, j], kind="stable")
            inverse = np.empty(n, dtype=np.int64)
            inverse[ranking] = np.arange(n, dtype=np.int64)
            for r, idx in enumerate(members):
                order = np.argsort(inverse[idx], kind="stable")
                positions = inverse[idx][order]  # 0-based positions in ranking
                k = len(positions)
                weights = ra[idx, j][order]
                denom = weights.sum()
                if denom <= 0:
                    weights = np.ones(k, dtype=np.float64)
                    denom = float(k)
                cdf_in = float((weights * (n - positions)).sum() / denom)
                cdf_out = float((n * (n + 1) / 2.0 - (n - positions).sum()) / (n - k))
                scores[r, j] = cdf_in - cdf_out
        if normalize:
            # GSVA divides by the global range; it does not subtract the minimum.
            span = float(scores.max() - scores.min())
            if span > 0:
                scores = scores / span
            else:
                scores = np.zeros_like(scores)
        form = make_form(
            scores.T, [sample_dim, set_dim],
            {sample_dim: axis_labels(samples, sample_dim),
             set_dim: axis_labels(kept, set_dim)},
        )
        ctx[out_name] = form
        self._export_data = {
            "n_samples": len(samples), "sets_scored": kept,
            "sets_skipped": skipped, "alpha": alpha,
            "normalize": normalize, "min_size": min_size,
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "n_samples": len(samples), "sets_scored": len(kept),
        }

    def export(self, ctx: Context) -> dict:
        return self._export_data
