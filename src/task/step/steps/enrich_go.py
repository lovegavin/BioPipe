# src/task/step/steps/enrich_go.py
"""GO term enrichment by the hypergeometric test.

Given a hit set and a background universe, both expressed as binary
gene x term matrices, this step computes for every term:

    N          total genes in the universe
    n          total genes in the hit set
    K          genes annotated to the term in the universe
    k          genes annotated to the term in the hit set
    expected   n * K / N
    P          P(X >= k | hypergeometric(N, K, n))
    Q          P adjusted by the requested multiple-testing method

The output is a term x statistic matrix, one row per term retained.

Layout
------
    hits       dims: [gene_dim, term_dim]
    universe   dims: [gene_dim, term_dim]
    output     dims: [term_dim, "statistic"]

Both inputs must share the same term labels. The hit set's genes
must be a subset of the universe's genes; otherwise the caller must
restrict the universe first.

Params:
    gene_dim       : name of the gene dimension (default "gene")
    term_dim       : name of the term dimension (default "go_term")
    correction     : fdr | bonferroni | holm | hommel | fdr_by
                     (default "fdr")
    min_term_size  : drop terms with fewer than this many genes in
                     the universe (default 1)
    output         : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step


_CORRECTIONS = ("fdr", "bonferroni", "holm", "hommel", "fdr_by")
_STATISTIC_COLUMNS = ["term_size", "n_hit", "expected", "P_VALUE", "Q_VALUE"]


class EnrichGoStep(Step):
    """Hypergeometric enrichment of one term axis over two inputs."""

    name = "enrich_go"
    category = "analysis"
    icon = "Intersect"
    inputs_arity = 2
    outputs = []
    input_contracts = [
        port(ndim=2, dims=[param("gene_dim", "gene"), param("term_dim", "go_term")]),
        port(ndim=2, dims=[param("gene_dim", "gene"), param("term_dim", "go_term")]),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {
            "ndim": 2,
            "numeric": True,
            "info_open": True,
            "axis_info_open": True,
        },
    }
    output_parameter = "output"
    parameters_schema = {
        "type": "object",
        "properties": {
            "gene_dim": {
                "type": "string",
                "title": "Gene dimension",
                "default": "gene",
            },
            "term_dim": {
                "type": "string",
                "title": "Term dimension",
                "default": "go_term",
            },
            "correction": {
                "type": "string",
                "title": "Multiple-testing correction",
                "enum": list(_CORRECTIONS),
                "default": "fdr",
            },
            "min_term_size": {
                "type": "integer",
                "title": "Minimum term size",
                "minimum": 1,
                "default": 1,
            },
            "output": {
                "type": "string",
                "title": "Output key",
            },
        },
    }

    def run(self, ctx: Context, inputs) -> None:
        hits, universe = inputs
        gene_dim = ctx.step_params.get("gene_dim", "gene")
        term_dim = ctx.step_params.get("term_dim", "go_term")
        correction = ctx.step_params.get("correction", "fdr")
        min_term_size = int(ctx.step_params.get("min_term_size", 1))
        out_name = ctx.step_params.get("output", self.name)

        if correction not in _CORRECTIONS:
            raise StepError(
                f"enrich_go: correction must be one of "
                f"{list(_CORRECTIONS)}, got {correction!r}"
            )
        if min_term_size < 1:
            raise StepError(
                f"enrich_go: min_term_size must be >= 1, "
                f"got {min_term_size}"
            )

        for label, form in (("hits", hits), ("universe", universe)):
            if form.data.ndim != 2:
                raise StepError(
                    f"enrich_go: {label} must be 2D, "
                    f"got ndim={form.data.ndim}"
                )
            if gene_dim not in form.dims:
                raise StepError(
                    f"enrich_go: gene_dim '{gene_dim}' not in "
                    f"{label} dims {form.dims}"
                )
            if term_dim not in form.dims:
                raise StepError(
                    f"enrich_go: term_dim '{term_dim}' not in "
                    f"{label} dims {form.dims}"
                )

        if set(universe.labels[term_dim]) != set(hits.labels[term_dim]):
            raise StepError(
                "enrich_go: hits and universe must share the same "
                "term labels"
            )

        # --- Reorient both to [gene, term]. ---
        universe_data = np.asarray(universe.data, dtype=np.float64)
        hits_data = np.asarray(hits.data, dtype=np.float64)

        if universe.dims.index(gene_dim) == 1:
            universe_data = universe_data.T
        if hits.dims.index(gene_dim) == 1:
            hits_data = hits_data.T

        # --- Align terms: use universe's order. ---
        universe_terms = universe.labels[term_dim]
        hits_terms = hits.labels[term_dim]
        term_order = sorted(universe_terms.items(), key=lambda kv: kv[1])
        term_ids = [t for t, _ in term_order]
        hits_col_positions = [hits_terms[t] for t in term_ids]

        universe_binary = universe_data > 0
        hits_selected = hits_data[:, hits_col_positions] > 0

        # --- Align genes: hits genes must be subset of universe genes. ---
        universe_genes = universe.labels[gene_dim]
        hits_genes = hits.labels[gene_dim]

        N = universe_binary.shape[0]
        n = hits_selected.shape[0]

        missing = [g for g in hits_genes if g not in universe_genes]
        if missing:
            raise StepError(
                f"enrich_go: {len(missing)} hit genes are not in the "
                f"universe (first: {missing[0]!r}). Restrict the "
                f"universe before calling enrich_go."
            )

        K = universe_binary.sum(axis=0).astype(np.int64)
        k = hits_selected.sum(axis=0).astype(np.int64)

        keep = K >= min_term_size
        if not keep.any():
            raise StepError(
                f"enrich_go: no term has at least {min_term_size} "
                f"genes in the universe"
            )

        K_kept = K[keep]
        k_kept = k[keep]
        term_ids_kept = [t for t, kp in zip(term_ids, keep) if kp]

        # --- Hypergeometric survival function. ---
        from scipy.stats import hypergeom

        with np.errstate(invalid="ignore"):
            pvals = hypergeom.sf(k_kept - 1, N, K_kept, n)
        pvals = np.clip(pvals, 0.0, 1.0)

        expected = n * K_kept / N

        qvals = _correct(pvals, correction)

        stat_matrix = np.column_stack([
            K_kept.astype(np.float32),
            k_kept.astype(np.float32),
            expected.astype(np.float32),
            pvals.astype(np.float32),
            qvals.astype(np.float32),
        ])

        from src.reader.readers._labels import unique_labels

        out_form = Form(
            data=stat_matrix,
            dims=[term_dim, "statistic"],
            labels={
                term_dim: unique_labels(
                    term_ids_kept, term_dim, "enrich_go"
                ),
                "statistic": {
                    name: i for i, name in enumerate(_STATISTIC_COLUMNS)
                },
            },
            info={"missing_code": np.nan},
        )
        out_form.validate()
        ctx[out_name] = out_form

        n_significant = int((qvals < 0.05).sum())

        self._export_data = {
            "gene_dim": gene_dim,
            "term_dim": term_dim,
            "correction": correction,
            "min_term_size": min_term_size,
            "n_universe_genes": int(N),
            "n_hit_genes": int(n),
            "n_terms_total": int(len(term_ids)),
            "n_terms_tested": int(len(term_ids_kept)),
            "n_terms_significant": n_significant,
            "statistic_columns": list(_STATISTIC_COLUMNS),
            "results": [
                {
                    "term": term_ids_kept[i],
                    "term_size": int(K_kept[i]),
                    "n_hit": int(k_kept[i]),
                    "expected": float(expected[i]),
                    "P_VALUE": float(pvals[i]),
                    "Q_VALUE": float(qvals[i]),
                }
                for i in range(len(term_ids_kept))
            ],
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "n_terms_tested": int(len(term_ids_kept)),
            "n_significant": n_significant,
            "correction": correction,
        }

        print(
            f"[enrich_go] N={N} n={n} terms={len(term_ids_kept)} "
            f"significant(q<0.05)={n_significant}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _correct(pvalues, method):
    from statsmodels.stats.multitest import multipletests

    method_map = {
        "fdr": "fdr_bh",
        "bonferroni": "bonferroni",
        "holm": "holm",
        "hommel": "hommel",
        "fdr_by": "fdr_by",
    }
    if pvalues.size == 0:
        return pvalues
    _, qvalues, _, _ = multipletests(pvalues, method=method_map[method])
    return qvalues
