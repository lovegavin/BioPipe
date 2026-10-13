# tasks/enrich_go_demo/test_enrich_go.py
"""Correctness tests for enrich_go.

Run:
    python tasks/enrich_go_demo/test_enrich_go.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.stats import hypergeom

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                       # noqa: E402
from src.task.step.steps.enrich_go import EnrichGoStep     # noqa: E402


class FakeContext:
    def __init__(self, params):
        self.step_params = dict(params)
        self.forms = {}
        self.metadata = {}
        self.memory = None

    def __setitem__(self, name, form):
        form.validate()
        self.forms[name] = form

    def __getitem__(self, name):
        return self.forms[name]


def make_matrix(gene_labels, term_labels, data):
    """Build a binary matrix Form with the given labels and data."""
    data = np.asarray(data, dtype=np.float32)
    return Form(
        data=data,
        dims=["gene", "go_term"],
        labels={
            "gene": {g: i for i, g in enumerate(gene_labels)},
            "go_term": {t: i for i, t in enumerate(term_labels)},
        },
        info={"missing_code": np.nan},
    )


def run(hits, universe, params):
    ctx = FakeContext(params)
    step = EnrichGoStep()
    step.run(ctx, [hits, universe])
    return ctx.forms[params.get("output", "enrich_go")], step.export(ctx)


def _stat(out, name):
    col = out.labels["statistic"][name]
    return out.data[:, col]


# ------------------------------------------------------------------ #
# Hand-computed hypergeometric
# ------------------------------------------------------------------ #

def test_hypergeometric_matches_scipy():
    """Universe 5 genes, 3 terms; hits 3 genes. Manually computed."""
    genes = ["g0", "g1", "g2", "g3", "g4"]
    terms = ["GO:1", "GO:2", "GO:3"]

    # Universe: term GO:1 -> g0,g1,g2; GO:2 -> g3,g4; GO:3 -> g0.
    universe_data = [
        [1, 0, 1],  # g0
        [1, 0, 0],  # g1
        [1, 0, 0],  # g2
        [0, 1, 0],  # g3
        [0, 1, 0],  # g4
    ]

    # Hits: g0, g1, g3. So k = [2, 1, 1].
    hits_data = [
        [1, 0, 1],  # g0
        [1, 0, 0],  # g1
        [0, 1, 0],  # g3
    ]

    universe = make_matrix(genes, terms, universe_data)
    hits = make_matrix(["g0", "g1", "g3"], terms, hits_data)

    out, exp = run(hits, universe, {
        "output": "o",
        "min_term_size": 1,
    })

    # N=5, n=3
    # term GO:1: K=3, k=2 -> P(X>=2 | 5,3,3) = 6/10 = 0.6
    # term GO:2: K=2, k=1 -> P(X>=1 | 5,2,3) = 0.9
    # term GO:3: K=1, k=1 -> P(X>=1 | 5,1,3) = 0.6
    expected_p = {
        "GO:1": hypergeom.sf(1, 5, 3, 3),
        "GO:2": hypergeom.sf(0, 5, 2, 3),
        "GO:3": hypergeom.sf(0, 5, 1, 3),
    }

    term_sizes = dict(zip(_term_ids(out), _stat(out, "term_size")))
    n_hits = dict(zip(_term_ids(out), _stat(out, "n_hit")))
    pvals = dict(zip(_term_ids(out), _stat(out, "P_VALUE")))

    assert term_sizes == {"GO:1": 3.0, "GO:2": 2.0, "GO:3": 1.0}
    assert n_hits == {"GO:1": 2.0, "GO:2": 1.0, "GO:3": 1.0}
    for term, expected_p_value in expected_p.items():
        assert abs(pvals[term] - expected_p_value) < 1e-6, (
            f"{term}: got {pvals[term]}, expected {expected_p_value}"
        )
    assert exp["n_universe_genes"] == 5
    assert exp["n_hit_genes"] == 3
    assert exp["n_terms_tested"] == 3
    print("PASS test_hypergeometric_matches_scipy")


def test_enrichment_detects_overrepresentation():
    """A term that is enriched in hits should have a low p-value."""
    genes = [f"g{i}" for i in range(100)]
    terms = ["enriched", "background"]

    universe_data = np.zeros((100, 2), dtype=np.float32)
    universe_data[:10, 0] = 1  # enriched term has 10 genes
    universe_data[:, 1] = 1    # background term has all 100 genes

    hits_data = np.zeros((10, 2), dtype=np.float32)
    hits_data[:, 0] = 1        # all 10 hits are in enriched
    hits_data[:, 1] = 1        # all 10 hits are in background

    universe = make_matrix(genes, terms, universe_data)
    hits = make_matrix([f"g{i}" for i in range(10)], terms, hits_data)

    out, _ = run(hits, universe, {"output": "o", "min_term_size": 1})

    pvals = dict(zip(_term_ids(out), _stat(out, "P_VALUE")))
    assert pvals["enriched"] < 0.01
    assert pvals["background"] > 0.5
    print("PASS test_enrichment_detects_overrepresentation")


def test_min_term_size_filters():
    genes = ["g0", "g1", "g2"]
    terms = ["big", "small"]
    universe_data = [
        [1, 1],
        [1, 0],
        [1, 0],
    ]
    hits_data = [
        [1, 1],
        [1, 0],
    ]
    universe = make_matrix(genes, terms, universe_data)
    hits = make_matrix(["g0", "g1"], terms, hits_data)

    out, exp = run(hits, universe, {"output": "o", "min_term_size": 2})
    assert list(out.labels["go_term"].keys()) == ["big"]
    assert exp["n_terms_tested"] == 1
    print("PASS test_min_term_size_filters")


def test_term_label_order_follows_universe():
    genes = ["g0", "g1"]
    terms = ["GO:z", "GO:a", "GO:m"]
    universe_data = [
        [1, 0, 1],
        [0, 1, 0],
    ]
    hits_data = [
        [1, 0, 1],
        [0, 1, 0],
    ]
    universe = make_matrix(genes, terms, universe_data)
    hits = make_matrix(genes, terms, hits_data)

    out, _ = run(hits, universe, {"output": "o", "min_term_size": 1})
    # Order preserved from universe's first-appearance order, not sorted.
    assert _term_ids(out) == ["GO:z", "GO:a", "GO:m"]
    print("PASS test_term_label_order_follows_universe")


# ------------------------------------------------------------------ #
# Structural checks
# ------------------------------------------------------------------ #

def test_output_dims_and_labels():
    genes = ["g0", "g1"]
    terms = ["GO:1"]
    universe = make_matrix(genes, terms, [[1], [1]])
    hits = make_matrix(genes, terms, [[1], [0]])

    out, _ = run(hits, universe, {"output": "o", "min_term_size": 1})
    assert out.dims == ["go_term", "statistic"]
    assert list(out.labels["statistic"].keys()) == [
        "term_size", "n_hit", "expected", "P_VALUE", "Q_VALUE",
    ]
    print("PASS test_output_dims_and_labels")


def test_expected_value_equals_nK_over_N():
    genes = [f"g{i}" for i in range(10)]
    terms = ["GO:1"]
    universe_data = np.zeros((10, 1), dtype=np.float32)
    universe_data[:4, 0] = 1
    hits_data = np.zeros((5, 1), dtype=np.float32)
    hits_data[:2, 0] = 1

    universe = make_matrix(genes, terms, universe_data)
    hits = make_matrix([f"g{i}" for i in range(5)], terms, hits_data)

    out, _ = run(hits, universe, {"output": "o", "min_term_size": 1})
    # N=10, n=5, K=4 -> expected = 5*4/10 = 2.0
    assert abs(_stat(out, "expected")[0] - 2.0) < 1e-6
    print("PASS test_expected_value_equals_nK_over_N")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_hits_gene_outside_universe_raises():
    universe = make_matrix(["g0", "g1"], ["GO:1"], [[1], [1]])
    hits = make_matrix(["g0", "gX"], ["GO:1"], [[1], [1]])

    try:
        run(hits, universe, {"output": "o", "min_term_size": 1})
    except StepError as exc:
        assert "not in the universe" in str(exc)
        print("PASS test_hits_gene_outside_universe_raises")
        return
    raise AssertionError("did not raise on gene outside universe")


def test_term_mismatch_raises():
    universe = make_matrix(["g0"], ["GO:1"], [[1]])
    hits = make_matrix(["g0"], ["GO:2"], [[1]])

    try:
        run(hits, universe, {"output": "o", "min_term_size": 1})
    except StepError as exc:
        assert "same term labels" in str(exc)
        print("PASS test_term_mismatch_raises")
        return
    raise AssertionError("did not raise on term mismatch")


def test_all_terms_below_min_size_raises():
    universe = make_matrix(["g0"], ["GO:1"], [[1]])
    hits = make_matrix(["g0"], ["GO:1"], [[1]])

    try:
        run(hits, universe, {"output": "o", "min_term_size": 5})
    except StepError as exc:
        assert "at least" in str(exc)
        print("PASS test_all_terms_below_min_size_raises")
        return
    raise AssertionError("did not raise when all terms are too small")


def test_bad_correction_raises():
    universe = make_matrix(["g0"], ["GO:1"], [[1]])
    hits = make_matrix(["g0"], ["GO:1"], [[1]])

    try:
        run(hits, universe, {"output": "o", "correction": "bogus"})
    except StepError as exc:
        assert "correction" in str(exc)
        print("PASS test_bad_correction_raises")
        return
    raise AssertionError("did not raise on bogus correction")


# ------------------------------------------------------------------ #
# Runner
# ------------------------------------------------------------------ #

def _term_ids(out):
    pos_to_label = {v: k for k, v in out.labels["go_term"].items()}
    return [pos_to_label[i] for i in range(out.data.shape[0])]


def main():
    tests = [
        test_hypergeometric_matches_scipy,
        test_enrichment_detects_overrepresentation,
        test_min_term_size_filters,
        test_term_label_order_follows_universe,
        test_output_dims_and_labels,
        test_expected_value_equals_nK_over_N,
        test_hits_gene_outside_universe_raises,
        test_term_mismatch_raises,
        test_all_terms_below_min_size_raises,
        test_bad_correction_raises,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {type(exc).__name__}: {exc}")
    print()
    print(f"{len(tests) - failed}/{len(tests)} passed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()