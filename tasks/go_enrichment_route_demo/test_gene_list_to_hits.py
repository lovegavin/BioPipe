"""Standalone verification of gene_list_to_hits and the GO route.

Run with: python tasks/go_enrichment_route_demo/test_gene_list_to_hits.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core import Form, StepError
from src.task.step.steps.gene_list_to_hits import GeneListToHitsStep
from src.task.step.steps.enrich_go import EnrichGoStep
from biopipe_sdk.testing import run_operator


def _make_universe(genes, terms, values):
    data = np.array(values, dtype=np.float32)
    return Form(
        data=data,
        dims=["gene", "go_term"],
        labels={
            "gene": {g: i for i, g in enumerate(genes)},
            "go_term": {t: i for i, t in enumerate(terms)},
        },
        info={"missing_code": np.nan},
    )


def test_hand_counted_hits():
    universe = _make_universe(
        genes=["A", "B", "C", "D"],
        terms=["T1", "T2"],
        values=[
            [1, 0],
            [1, 1],
            [0, 1],
            [0, 0],
        ],
    )
    hits = run_operator(GeneListToHitsStep, [universe], {"genes": ["A", "B", "D"]})
    assert hits.dims == ["gene", "go_term"]
    # Only A, B, D rows survive.
    assert set(hits.labels["gene"].keys()) == {"A", "B", "D"}
    assert hits.data.shape == (3, 2)
    assert np.array_equal(hits.data, np.array([
        [1, 0],
        [1, 1],
        [0, 0],
    ], dtype=np.float32))
    print("  hand-counted hits                    ok")


def test_missing_gene_rejected():
    universe = _make_universe(
        genes=["A", "B"], terms=["T1"], values=[[1], [0]],
    )
    try:
        run_operator(GeneListToHitsStep, [universe], {"genes": ["X"]})
        raise AssertionError("expected rejection")
    except AssertionError:
        raise
    except StepError as exc:
        assert "not in universe" in str(exc)
    print("  missing gene rejected                ok")


def test_enrich_go_hand_counted():
    # N=4 universe genes. n=2 hit genes (A, B).
    # T1 has K=2 annotated genes (A, B), k=2 hit.
    # P(X >= 2 | hypergeom(N=4, K=2, n=2)) = 1/6.
    universe = _make_universe(
        genes=["A", "B", "C", "D"],
        terms=["T1"],
        values=[[1], [1], [0], [0]],
    )
    hits = run_operator(
        GeneListToHitsStep, [universe], {"genes": ["A", "B"]},
    )
    out = run_operator(EnrichGoStep, [hits, universe], {
        "gene_dim": "gene",
        "term_dim": "go_term",
        "correction": "bonferroni",
        "min_term_size": 1,
    })
    stats = {n: i for n, i in out.labels["statistic"].items()}
    p = float(out.data[0, stats["P_VALUE"]])
    assert abs(p - 1.0 / 6.0) < 1e-6, p
    expected = 2 * 2 / 4
    assert abs(float(out.data[0, stats["expected"]]) - expected) < 1e-6
    print("  enrich_go hand-counted p-value       ok")


def test_full_chain_on_real_gaf():
    gaf = Path(__file__).parent / "input" / "goa_human.gaf.gz"
    if not gaf.exists():
        print("  full GAF chain (data missing)        skip")
        return
    from src.reader import read_source
    from src.task.step.steps.pivot import PivotStep

    form = read_source(
        gaf, dims=["annotation", "field"],
        labels={"annotation": "auto", "field": "builtin"},
    )
    universe = run_operator(PivotStep, [form], {
        "index_label": "db_object_symbol",
        "columns_label": "go_id",
        "index_name": "gene",
        "columns_name": "go_term",
        "agg": "first",
    })
    hits = run_operator(GeneListToHitsStep, [universe], {
        "genes": ["ATM", "ATR", "CHEK1", "CHEK2", "TP53",
                  "MDM2", "MDM4", "CDKN1A", "CDKN2A", "GADD45A"],
    })
    assert hits.data.shape[0] == 10
    assert hits.data.sum() > 0
    enriched = run_operator(EnrichGoStep, [hits, universe], {
        "gene_dim": "gene", "term_dim": "go_term",
        "correction": "fdr", "min_term_size": 5,
    })
    stats = list(enriched.labels["statistic"].keys())
    pvals = enriched.data[:, stats.index("P_VALUE")]
    assert np.all((pvals >= 0) & (pvals <= 1))
    print("  full GAF chain                       ok")


def main():
    print("gene_list_to_hits + GO route verification")
    test_hand_counted_hits()
    test_missing_gene_rejected()
    test_enrich_go_hand_counted()
    test_full_chain_on_real_gaf()
    print()
    print("all checks passed")


if __name__ == "__main__":
    main()
