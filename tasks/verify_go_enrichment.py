"""Independent verification of gene_list_to_hits and enrich_go.

Run with: python tasks/verify_go_enrichment.py
"""
import sys
from pathlib import Path

import numpy as np
from scipy.stats import hypergeom

sys.path.insert(0, ".")

from src.core import Form
from src.reader import read_source
from src.task.step.steps.pivot import PivotStep
from src.task.step.steps.gene_list_to_hits import GeneListToHitsStep
from src.task.step.steps.enrich_go import EnrichGoStep
from biopipe_sdk.testing import run_operator


checks = []


def record(name, ok, expected, actual):
    checks.append((name, bool(ok), str(expected)[:50], str(actual)[:50]))


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def main():
    gaf = Path("tasks/go_enrichment_route_demo/input/goa_human.gaf.gz")
    if not gaf.exists():
        print(f"missing {gaf}")
        sys.exit(1)

    section("1. gene_list_to_hits on synthetic universe")
    genes = ["A", "B", "C", "D", "E"]
    terms = ["T1", "T2", "T3"]
    values = [
        [1, 0, 0],
        [1, 1, 0],
        [0, 1, 0],
        [0, 0, 1],
        [0, 0, 0],
    ]
    universe = Form(
        data=np.array(values, dtype=np.float32),
        dims=["gene", "go_term"],
        labels={
            "gene": {g: i for i, g in enumerate(genes)},
            "go_term": {t: i for i, t in enumerate(terms)},
        },
        info={"missing_code": np.nan},
    )
    hits = run_operator(GeneListToHitsStep, [universe], {"genes": ["A", "C", "E"]})
    expected_rows = {"A", "C", "E"}
    record("gene_list_to_hits keeps only hit genes",
            set(hits.labels["gene"].keys()) == expected_rows,
            sorted(expected_rows), sorted(hits.labels["gene"].keys()))
    expected = np.array([
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 0],
    ], dtype=np.float32)
    record("gene_list_to_hits exact matrix",
            np.array_equal(hits.data, expected),
            "exact", "match" if np.array_equal(hits.data, expected) else "mismatch")

    section("2. enrich_go hypergeometric vs scipy")
    N = 20
    universe_mat = np.zeros((N, 3), dtype=np.float32)
    universe_mat[:8, 0] = 1
    universe_mat[:5, 1] = 1
    universe_mat[:2, 2] = 1
    hit_rows = [0, 1, 2, 3]
    hits_mat = np.zeros((len(hit_rows), 3), dtype=np.float32)
    hits_mat[0:3, 0] = 1
    hits_mat[0, 1] = 1

    K = universe_mat.sum(axis=0).astype(int)
    k = hits_mat.sum(axis=0).astype(int)
    n = len(hit_rows)

    universe_form = Form(
        data=universe_mat,
        dims=["gene", "go_term"],
        labels={
            "gene": {f"G{i}": i for i in range(N)},
            "go_term": {f"T{i}": i for i in range(3)},
        },
        info={"missing_code": np.nan},
    )
    hits_form = Form(
        data=hits_mat,
        dims=["gene", "go_term"],
        labels={
            "gene": {f"G{hit_rows[i]}": i for i in range(len(hit_rows))},
            "go_term": {f"T{i}": i for i in range(3)},
        },
        info={"missing_code": np.nan},
    )

    out = run_operator(EnrichGoStep, [hits_form, universe_form], {
        "gene_dim": "gene", "term_dim": "go_term",
        "correction": "bonferroni", "min_term_size": 1,
    })
    stats = {n: i for n, i in out.labels["statistic"].items()}
    pvals = out.data[:, stats["P_VALUE"]]
    expected_p = [float(hypergeom.sf(int(k[i]) - 1, N, int(K[i]), n))
                  for i in range(3)]
    ok = all(abs(float(pvals[i]) - expected_p[i]) < 1e-6 for i in range(3))
    record("enrich_go p-values match scipy.hypergeom.sf",
            ok, str([f"{e:.4f}" for e in expected_p]),
            str([f"{float(p):.4f}" for p in pvals]))

    section("3. Full chain on real GAF")
    form = read_source(
        gaf, dims=["annotation", "field"],
        labels={"annotation": "auto", "field": "builtin"},
    )
    universe_real = run_operator(PivotStep, [form], {
        "index_label": "db_object_symbol",
        "columns_label": "go_id",
        "index_name": "gene",
        "columns_name": "go_term",
        "agg": "first",
    })
    record("real GAF universe has genes",
            universe_real.data.shape[0] > 1000,
            "> 1000", universe_real.data.shape[0])

    hit_genes = ["ATM", "ATR", "CHEK1", "CHEK2", "TP53",
                 "MDM2", "MDM4", "CDKN1A", "CDKN2A", "GADD45A"]
    hits_real = run_operator(GeneListToHitsStep, [universe_real], {"genes": hit_genes})
    record("real hits row count equals hit genes",
            hits_real.data.shape[0] == len(hit_genes),
            len(hit_genes), hits_real.data.shape[0])
    record("real hits contain only 0/1",
            bool(np.isin(hits_real.data, [0.0, 1.0]).all()),
            "0 or 1", "ok")

    enriched = run_operator(EnrichGoStep, [hits_real, universe_real], {
        "gene_dim": "gene", "term_dim": "go_term",
        "correction": "fdr", "min_term_size": 5,
    })
    s = list(enriched.labels["statistic"].keys())
    pvals_real = enriched.data[:, s.index("P_VALUE")]
    qvals_real = enriched.data[:, s.index("Q_VALUE")]
    record("real enrichment: all p in [0, 1]",
            bool(((pvals_real >= 0) & (pvals_real <= 1)).all()),
            "all in [0, 1]", "ok")
    record("real enrichment: all q in [0, 1]",
            bool(((qvals_real >= 0) & (qvals_real <= 1)).all()),
            "all in [0, 1]", "ok")
    record("real enrichment: at least one q < 0.05",
            bool((qvals_real < 0.05).any()),
            "> 0", int((qvals_real < 0.05).sum()))
    record("real enrichment: p <= q for every term (BH property)",
            bool((pvals_real <= qvals_real + 1e-6).all()),
            "all p <= q", "ok")

    print()
    print("=" * 78)
    print("Verification summary")
    print("=" * 78)
    print(f"{'':<4}{'check':<54}{'expected':>12}{'actual':>14}")
    print("-" * 78)
    for name, ok, exp, act in checks:
        status = "PASS" if ok else "FAIL"
        print(f"{status}  {name:<54}{exp:>12}{act:>14}")
    print("-" * 78)
    passed = sum(1 for _, ok, _, _ in checks if ok)
    print(f"{passed}/{len(checks)} checks passed")
    if passed < len(checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
