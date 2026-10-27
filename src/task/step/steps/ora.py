# src/task/step/steps/ora.py
"""Over-representation analysis (hypergeometric test) for gene sets.

Inputs
------
stats : 2D [gene, statistic] with columns such as log2FC and Q_VALUE.
sets  : 2D [gene, gene_set] binary membership (for example GmtReader).

The hit set is selected from ``stats`` by adjusted p-value and absolute
log fold change. The universe is every gene present in ``stats``; genes
in a set that are absent from the universe are ignored and counted in
the export.

This is the classical Fisher/hypergeometric ORA, not GSEA.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import hypergeom

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

_COLUMNS = ["set_size", "n_hit", "expected", "P_VALUE", "Q_VALUE"]
_CORRECTIONS = ("fdr", "bonferroni", "holm", "hommel", "fdr_by")
_DIRECTIONS = ("up", "down", "both")


class OraStep(Step):
    name = "ora"
    title = "Gene-set ORA"
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
            "p_label": {"type": "string", "default": "Q_VALUE"},
            "lfc_label": {"type": "string", "default": "log2FC"},
            "p_threshold": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.05},
            "lfc_threshold": {"type": "number", "minimum": 0, "default": 0.0},
            "direction": {"type": "string", "enum": list(_DIRECTIONS), "default": "both"},
            "correction": {"type": "string", "enum": list(_CORRECTIONS), "default": "fdr"},
            "min_set_size": {"type": "integer", "minimum": 1, "default": 1},
            "output": {"type": "string"},
        },
        "required": ["p_label", "lfc_label"],
    }

    def run(self, ctx: Context, inputs) -> None:
        stats, sets = inputs
        gene_dim = ctx.step_params.get("gene_dim", "gene")
        stat_dim = ctx.step_params.get("stat_dim", "statistic")
        set_dim = ctx.step_params.get("gene_set_dim", "gene_set")
        p_label = ctx.step_params["p_label"]
        lfc_label = ctx.step_params["lfc_label"]
        p_threshold = float(ctx.step_params.get("p_threshold", 0.05))
        lfc_threshold = float(ctx.step_params.get("lfc_threshold", 0.0))
        direction = ctx.step_params.get("direction", "both")
        correction = ctx.step_params.get("correction", "fdr")
        min_size = int(ctx.step_params.get("min_set_size", 1))
        out_name = ctx.step_params.get("output", self.name)
        require_dims(stats, gene_dim, stat_dim, label="stats")
        require_dims(sets, gene_dim, set_dim, label="sets")
        columns = stats.labels[stat_dim]
        for label in (p_label, lfc_label):
            if label not in columns:
                raise StepError(f"ora: column {label!r} not in {sorted(columns)}")
        if direction not in _DIRECTIONS:
            raise StepError(f"ora: direction must be one of {_DIRECTIONS}")
        if correction not in _CORRECTIONS:
            raise StepError(f"ora: correction must be one of {_CORRECTIONS}")
        if min_size < 1:
            raise StepError("ora: min_set_size must be >= 1")

        stat_data = reorder(stats, gene_dim, stat_dim)
        genes = labels_in_order(stats, gene_dim)
        p_values = stat_data[:, columns[p_label]]
        lfc = stat_data[:, columns[lfc_label]]
        if len(p_values) != len(genes):
            raise StepError("ora: stats data and gene labels disagree")
        hit = np.isfinite(p_values) & (p_values <= p_threshold) & (np.abs(lfc) >= lfc_threshold)
        if direction == "up":
            hit &= lfc > 0
        elif direction == "down":
            hit &= lfc < 0
        universe_n = len(genes)
        hit_n = int(hit.sum())
        if hit_n == 0:
            raise StepError("ora: no genes pass the hit thresholds")

        set_data = reorder(sets, gene_dim, set_dim)
        set_genes = labels_in_order(sets, gene_dim)
        set_names = labels_in_order(sets, set_dim)
        # Align set rows to the stats gene order; genes absent from stats are ignored.
        set_pos = {gene: i for i, gene in enumerate(set_genes)}
        aligned = np.zeros((universe_n, len(set_names)), dtype=bool)
        ignored = 0
        for row, gene in enumerate(genes):
            src = set_pos.get(gene)
            if src is None:
                continue
            aligned[row, :] = set_data[src, :] > 0
        stat_gene_set = set(genes)
        ignored = sum(1 for gene in set_genes if gene not in stat_gene_set)

        keep = aligned.sum(axis=0) >= min_size
        if not keep.any():
            raise StepError(f"ora: no gene set has at least {min_size} genes in the stats universe")
        K = aligned[:, keep].sum(axis=0)
        k = (aligned[:, keep] & hit[:, None]).sum(axis=0)
        expected = hit_n * K / universe_n
        pvals = np.clip(hypergeom.sf(k - 1, universe_n, K, hit_n), 0.0, 1.0)
        qvals = correct(pvals, correction)
        kept_names = [name for name, present in zip(set_names, keep) if present]
        data = np.column_stack([K, k, expected, pvals, qvals]).astype(np.float32)
        form = make_form(
            data,
            [set_dim, "statistic"],
            {set_dim: axis_labels(kept_names, set_dim),
             "statistic": {name: i for i, name in enumerate(_COLUMNS)}},
        )
        ctx[out_name] = form
        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "universe": universe_n, "hits": hit_n, "sets_tested": len(kept_names),
            "significant": int((qvals < 0.05).sum()),
        }
        self._export_data = {
            "universe": universe_n, "hits": hit_n,
            "sets_total": len(set_names), "sets_tested": len(kept_names),
            "genes_ignored": int(ignored),
            "significant": int((qvals < 0.05).sum()),
            "results": [
                {"set": name, "set_size": int(K[i]), "n_hit": int(k[i]),
                 "expected": float(expected[i]), "P_VALUE": float(pvals[i]),
                 "Q_VALUE": float(qvals[i])}
                for i, name in enumerate(kept_names)
            ],
        }
        print(f"[ora] universe={universe_n} hits={hit_n} sets={len(kept_names)}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
