# src/task/step/steps/gsea.py
"""Preranked Gene Set Enrichment Analysis (GSEA).

This is the classical weighted Kolmogorov-Smirnov enrichment score
(Subramanian et al. 2005), followed by gene-set permutation p-values
and BH correction. It is intentionally labelled *preranked*: it does
not reorder samples or estimate per-sample phenotypes.

Inputs
------
ranked : [gene, statistic] with a ranking column (default log2FC)
sets   : [gene, gene_set] binary membership

The gene-set permutation null is the standard choice for preranked
GSEA when sample-level expression is not available. The number of
permutations is explicit and seeded; results are reproducible.

This implementation is independent of fgsea/clusterProfiler. The test
suite compares the enrichment-score calculation and null behavior.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import (
    axis_labels,
    correct,
    labels_in_order,
    make_form,
    reorder,
    require_dims,
)

_COLUMNS = ["ES", "NES", "P_VALUE", "Q_VALUE", "set_size", "n_permutations"]
_CORRECTIONS = ("fdr", "bonferroni", "holm", "hommel", "fdr_by")


def _enrichment_score(rank_values, hits, weight):
    n = len(rank_values)
    nh = int(hits.sum())
    if nh == 0 or nh == n:
        return 0.0
    hit_weight = np.abs(rank_values[hits]) ** weight
    total = hit_weight.sum()
    if total <= 0:
        hit_weight = np.ones(nh, dtype=np.float64)
        total = nh
    step = np.zeros(n, dtype=np.float64)
    step[hits] = hit_weight / total
    step[~hits] -= 1.0 / (n - nh)
    running = np.cumsum(step)
    high = running.max()
    low = running.min()
    return float(high if high >= -low else low)


class GseaStep(Step):
    name = "gsea"
    title = "Preranked GSEA"
    category = "Analysis"
    builtin_package = "biopipe-expression"
    inputs_arity = 2
    outputs = []
    input_contracts = [
        port(ndim=2, dims=[param("gene_dim", "gene"), param("stat_dim", "statistic")]),
        port(ndim=2, dims=[param("gene_dim", "gene"), param("gene_set_dim", "gene_set")]),
    ]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": False, "axis_info_open": False,
        "info": {"missing_code": {"type": ["number", "null"]}}}}
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "gene_dim": {"type": "string", "default": "gene"},
            "stat_dim": {"type": "string", "default": "statistic"},
            "gene_set_dim": {"type": "string", "default": "gene_set"},
            "rank_label": {"type": "string", "default": "log2FC"},
            "weight": {"type": "number", "minimum": 0, "default": 1.0},
            "n_permutations": {"type": "integer", "minimum": 10, "default": 1000},
            "seed": {"type": "integer", "default": 0},
            "min_set_size": {"type": "integer", "minimum": 1, "default": 5},
            "max_set_size": {"type": "integer", "minimum": 1, "default": 500},
            "correction": {"type": "string", "enum": list(_CORRECTIONS), "default": "fdr"},
            "output": {"type": "string"},
        },
    }

    def run(self, ctx: Context, inputs) -> None:
        ranked, sets = inputs
        gene_dim = ctx.step_params.get("gene_dim", "gene")
        stat_dim = ctx.step_params.get("stat_dim", "statistic")
        set_dim = ctx.step_params.get("gene_set_dim", "gene_set")
        rank_label = ctx.step_params.get("rank_label", "log2FC")
        weight = float(ctx.step_params.get("weight", 1.0))
        n_perm = int(ctx.step_params.get("n_permutations", 1000))
        seed = int(ctx.step_params.get("seed", 0))
        min_size = int(ctx.step_params.get("min_set_size", 5))
        max_size = int(ctx.step_params.get("max_set_size", 500))
        correction = ctx.step_params.get("correction", "fdr")
        out_name = ctx.step_params.get("output", self.name)
        require_dims(ranked, gene_dim, stat_dim, label="ranked")
        require_dims(sets, gene_dim, set_dim, label="sets")
        if rank_label not in ranked.labels[stat_dim]:
            raise StepError(f"gsea: rank column {rank_label!r} not found")
        if n_perm < 10:
            raise StepError("gsea: n_permutations must be >= 10")
        if min_size < 1 or max_size < min_size:
            raise StepError("gsea: invalid min/max set size")
        if correction not in _CORRECTIONS:
            raise StepError(f"gsea: unknown correction {correction!r}")
        values = reorder(ranked, gene_dim, stat_dim)[:, ranked.labels[stat_dim][rank_label]]
        genes = labels_in_order(ranked, gene_dim)
        finite = np.isfinite(values)
        genes = [gene for gene, ok in zip(genes, finite) if ok]
        values = values[finite]
        order = np.argsort(-values, kind="stable")
        genes = [genes[i] for i in order]
        values = values[order]
        n = len(genes)
        if n < 2:
            raise StepError("gsea: fewer than two ranked genes")
        set_data = reorder(sets, gene_dim, set_dim)
        set_genes = labels_in_order(sets, gene_dim)
        set_names = labels_in_order(sets, set_dim)
        pos = {gene: i for i, gene in enumerate(set_genes)}
        rows = np.zeros((n, len(set_names)), dtype=bool)
        for i, gene in enumerate(genes):
            j = pos.get(gene)
            if j is not None:
                rows[i, :] = set_data[j, :] > 0
        sizes = rows.sum(axis=0)
        keep = (sizes >= min_size) & (sizes <= max_size)
        if not keep.any():
            raise StepError("gsea: no gene set passes the size filter")
        names = [name for name, ok in zip(set_names, keep) if ok]
        rows = rows[:, keep]
        observed = np.asarray([_enrichment_score(values, rows[:, j], weight)
                               for j in range(rows.shape[1])])
        rng = np.random.default_rng(seed)
        perm = np.empty((n_perm, rows.shape[1]), dtype=np.float64)
        for p in range(n_perm):
            shuffled = values[rng.permutation(n)]
            for j in range(rows.shape[1]):
                perm[p, j] = _enrichment_score(shuffled, rows[:, j], weight)
        pvals = np.empty(rows.shape[1], dtype=np.float64)
        nes = np.empty(rows.shape[1], dtype=np.float64)
        for j, es in enumerate(observed):
            if es >= 0:
                null = perm[:, j][perm[:, j] >= 0]
                pvals[j] = (1.0 + np.count_nonzero(perm[:, j] >= es)) / (n_perm + 1.0)
                nes[j] = es / null.mean() if null.size and null.mean() > 0 else 0.0
            else:
                null = perm[:, j][perm[:, j] < 0]
                pvals[j] = (1.0 + np.count_nonzero(perm[:, j] <= es)) / (n_perm + 1.0)
                nes[j] = es / abs(null.mean()) if null.size and null.mean() < 0 else 0.0
        qvals = correct(pvals, correction)
        data = np.column_stack([observed, nes, pvals, qvals, rows.sum(axis=0),
                                np.full(len(names), n_perm)]).astype(np.float32)
        form = make_form(
            data, [set_dim, "statistic"],
            {set_dim: axis_labels(names, set_dim),
             "statistic": {name: i for i, name in enumerate(_COLUMNS)}},
        )
        ctx[out_name] = form
        self._export_data = {
            "n_genes": n, "sets_tested": len(names), "n_permutations": n_perm,
            "seed": seed, "weight": weight,
            "significant": int((qvals < 0.05).sum()),
            "results": [
                {"set": name, "ES": float(observed[i]), "NES": float(nes[i]),
                 "P_VALUE": float(pvals[i]), "Q_VALUE": float(qvals[i]),
                 "set_size": int(rows[:, i].sum())}
                for i, name in enumerate(names)
            ],
        }
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "sets_tested": len(names), "significant": int((qvals < 0.05).sum()),
        }
        print(f"[gsea] genes={n} sets={len(names)} permutations={n_perm}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
