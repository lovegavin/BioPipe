# tasks/enrichment_plot_demo/test_enrichment_plot.py
"""Correctness tests for enrichment_plot.

Run:
    python tasks/enrichment_plot_demo/test_enrichment_plot.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                              # noqa: E402
from src.task.step.steps.enrichment_plot import EnrichmentPlotStep  # noqa: E402


class FakeContext:
    def __init__(self, params):
        self.step_params = dict(params)
        self.forms = {}
        self.metadata = {}
        self.memory = None
        self.out_dir = Path(tempfile.mkdtemp())

    def __setitem__(self, name, form):
        form.validate()
        self.forms[name] = form

    def __getitem__(self, name):
        return self.forms[name]


def make_enriched(terms, q_values, n_hits, term_sizes=None):
    if term_sizes is None:
        term_sizes = [10] * len(terms)
    data = np.column_stack([
        np.asarray(term_sizes, dtype=np.float32),
        np.asarray(n_hits, dtype=np.float32),
        np.asarray(n_hits, dtype=np.float32) * 0.1,
        np.asarray(q_values, dtype=np.float32),
        np.asarray(q_values, dtype=np.float32),
    ])
    return Form(
        data=data,
        dims=["go_term", "statistic"],
        labels={
            "go_term": {t: i for i, t in enumerate(terms)},
            "statistic": {
                "term_size": 0,
                "n_hit": 1,
                "expected": 2,
                "P_VALUE": 3,
                "Q_VALUE": 4,
            },
        },
        info={"missing_code": np.nan},
    )


def run(form, params):
    ctx = FakeContext(params)
    step = EnrichmentPlotStep()
    step.run(ctx, [form])
    return step.export(ctx), ctx


def test_writes_png_and_lists_top_terms():
    form = make_enriched(
        terms=["GO:a", "GO:b", "GO:c"],
        q_values=[0.5, 1e-6, 0.01],
        n_hits=[3, 15, 8],
    )
    exp, ctx = run(form, {
        "top_n": 2,
        "filename": "test.png",
        "output": "o",
    })
    assert exp["n_plotted"] == 2
    assert exp["plotted_terms"][0]["term"] == "GO:b"
    assert exp["plotted_terms"][1]["term"] == "GO:c"
    assert Path(exp["figure_path"]).exists()
    print("PASS test_writes_png_and_lists_top_terms")


def test_custom_dim_names():
    form = Form(
        data=np.array([[10.0, 5.0, 0.001, 0.005]], dtype=np.float32),
        dims=["pathway", "column"],
        labels={
            "pathway": {"KEGG:1": 0},
            "column": {
                "term_size": 0,
                "n_hit": 1,
                "P_VALUE": 2,
                "Q_VALUE": 3,
            },
        },
        info={"missing_code": np.nan},
    )
    exp, _ = run(form, {
        "term_dim": "pathway",
        "statistic_dim": "column",
        "top_n": 1,
        "filename": "custom.png",
        "output": "o",
    })
    assert exp["n_plotted"] == 1
    assert exp["plotted_terms"][0]["term"] == "KEGG:1"
    print("PASS test_custom_dim_names")


def test_nan_q_ranked_last():
    form = make_enriched(
        terms=["GO:a", "GO:b", "GO:c"],
        q_values=[0.01, np.nan, 0.5],
        n_hits=[5, 5, 5],
    )
    exp, _ = run(form, {
        "top_n": 1,
        "filename": "nan.png",
        "output": "o",
    })
    # Smallest finite Q is GO:a (0.01); NaN should be skipped
    assert exp["plotted_terms"][0]["term"] == "GO:a"
    print("PASS test_nan_q_ranked_last")


def test_missing_q_column_raises():
    form = Form(
        data=np.array([[10.0]], dtype=np.float32),
        dims=["go_term", "statistic"],
        labels={
            "go_term": {"GO:a": 0},
            "statistic": {"term_size": 0},
        },
        info={"missing_code": np.nan},
    )
    try:
        run(form, {"output": "o"})
    except StepError as exc:
        assert "Q_VALUE" in str(exc)
        print("PASS test_missing_q_column_raises")
        return
    raise AssertionError("did not raise on missing Q column")


def test_no_finite_q_raises():
    form = make_enriched(
        terms=["GO:a", "GO:b"],
        q_values=[np.nan, np.nan],
        n_hits=[0, 0],
    )
    try:
        run(form, {"output": "o"})
    except StepError as exc:
        assert "no finite" in str(exc)
        print("PASS test_no_finite_q_raises")
        return
    raise AssertionError("did not raise on all-NaN Q")


def test_bad_top_n_raises():
    form = make_enriched(
        terms=["GO:a"], q_values=[0.01], n_hits=[5],
    )
    try:
        run(form, {"top_n": 0, "output": "o"})
    except StepError as exc:
        assert "top_n" in str(exc)
        print("PASS test_bad_top_n_raises")
        return
    raise AssertionError("did not raise on bad top_n")


def main():
    tests = [
        test_writes_png_and_lists_top_terms,
        test_custom_dim_names,
        test_nan_q_ranked_last,
        test_missing_q_column_raises,
        test_no_finite_q_raises,
        test_bad_top_n_raises,
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