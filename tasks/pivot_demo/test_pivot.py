# tasks/pivot_demo/test_pivot.py
"""Correctness tests for pivot.

Run:
    python tasks/pivot_demo/test_pivot.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                     # noqa: E402
from src.reader.readers._encoder import LabelEncoder     # noqa: E402
from src.task.step.steps.pivot import PivotStep          # noqa: E402


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


def make_form(data, field_labels, encoders=None):
    data = np.asarray(data, dtype=np.float32)
    pair_labels = {f"p{i}": i for i in range(data.shape[0])}
    info = {"missing_code": np.nan}
    if encoders:
        info["encoders"] = {"field": encoders}
    return Form(
        data=data,
        dims=["pair", "field"],
        labels={
            "pair": pair_labels,
            "field": {lbl: i for i, lbl in enumerate(field_labels)},
        },
        info=info,
    )


def run(form, params):
    ctx = FakeContext(params)
    step = PivotStep()
    step.run(ctx, [form])
    return ctx.forms[params.get("output", "pivot")], step.export(ctx)


# ------------------------------------------------------------------ #
# Binary membership (no values column)
# ------------------------------------------------------------------ #

def test_pivot_binary_membership():
    gene_enc = LabelEncoder()
    gene_enc.fit_transform(["A", "A", "B"])
    go_enc = LabelEncoder()
    go_enc.fit_transform(["GO:1", "GO:2", "GO:1"])

    form = make_form(
        data=[
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"]],
            [gene_enc.mapping["A"], go_enc.mapping["GO:2"]],
            [gene_enc.mapping["B"], go_enc.mapping["GO:1"]],
        ],
        field_labels=["gene_symbol", "go_id"],
        encoders={"gene_symbol": gene_enc, "go_id": go_enc},
    )
    out, exp = run(form, {
        "index_label": "gene_symbol",
        "columns_label": "go_id",
        "index_name": "gene",
        "columns_name": "go_term",
        "agg": "sum",
        "output": "o",
    })
    assert out.dims == ["gene", "go_term"]
    assert out.labels["gene"] == {"A": 0, "B": 1}
    assert out.labels["go_term"] == {"GO:1": 0, "GO:2": 1}
    assert out.data.tolist() == [[1.0, 1.0], [1.0, 0.0]]
    assert exp["n_index"] == 2
    assert exp["n_columns"] == 2
    assert exp["n_nonzero"] == 3
    print("PASS test_pivot_binary_membership")


# ------------------------------------------------------------------ #
# Values column
# ------------------------------------------------------------------ #

def test_pivot_with_values_column():
    gene_enc = LabelEncoder()
    gene_enc.fit_transform(["A", "B"])
    go_enc = LabelEncoder()
    go_enc.fit_transform(["GO:1", "GO:1"])

    form = make_form(
        data=[
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"], 0.5],
            [gene_enc.mapping["B"], go_enc.mapping["GO:1"], 0.8],
        ],
        field_labels=["gene_symbol", "go_id", "score"],
        encoders={"gene_symbol": gene_enc, "go_id": go_enc},
    )
    out, _ = run(form, {
        "index_label": "gene_symbol",
        "columns_label": "go_id",
        "values_label": "score",
        "agg": "sum",
        "output": "o",
    })
    assert np.allclose(out.data, [[0.5], [0.8]], rtol=1e-6)
    print("PASS test_pivot_with_values_column")


def test_pivot_sum_aggregates_duplicates():
    gene_enc = LabelEncoder()
    gene_enc.fit_transform(["A", "A"])
    go_enc = LabelEncoder()
    go_enc.fit_transform(["GO:1", "GO:1"])

    form = make_form(
        data=[
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"], 2.0],
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"], 3.0],
        ],
        field_labels=["gene_symbol", "go_id", "score"],
        encoders={"gene_symbol": gene_enc, "go_id": go_enc},
    )
    out, _ = run(form, {
        "index_label": "gene_symbol",
        "columns_label": "go_id",
        "values_label": "score",
        "agg": "sum",
        "output": "o",
    })
    assert out.data[0, 0] == 5.0
    print("PASS test_pivot_sum_aggregates_duplicates")


def test_pivot_max_aggregates_duplicates():
    gene_enc = LabelEncoder()
    gene_enc.fit_transform(["A", "A"])
    go_enc = LabelEncoder()
    go_enc.fit_transform(["GO:1", "GO:1"])

    form = make_form(
        data=[
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"], 2.0],
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"], 5.0],
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"], 3.0],
        ],
        field_labels=["gene_symbol", "go_id", "score"],
        encoders={"gene_symbol": gene_enc, "go_id": go_enc},
    )
    out, _ = run(form, {
        "index_label": "gene_symbol",
        "columns_label": "go_id",
        "values_label": "score",
        "agg": "max",
        "output": "o",
    })
    assert out.data[0, 0] == 5.0
    print("PASS test_pivot_max_aggregates_duplicates")


def test_pivot_min_aggregates_duplicates():
    gene_enc = LabelEncoder()
    gene_enc.fit_transform(["A", "A"])
    go_enc = LabelEncoder()
    go_enc.fit_transform(["GO:1", "GO:1"])

    form = make_form(
        data=[
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"], 2.0],
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"], 5.0],
        ],
        field_labels=["gene_symbol", "go_id", "score"],
        encoders={"gene_symbol": gene_enc, "go_id": go_enc},
    )
    out, _ = run(form, {
        "index_label": "gene_symbol",
        "columns_label": "go_id",
        "values_label": "score",
        "agg": "min",
        "output": "o",
    })
    assert out.data[0, 0] == 2.0
    print("PASS test_pivot_min_aggregates_duplicates")


def test_pivot_first_aggregates_duplicates():
    gene_enc = LabelEncoder()
    gene_enc.fit_transform(["A", "A", "A"])
    go_enc = LabelEncoder()
    go_enc.fit_transform(["GO:1", "GO:1", "GO:1"])

    form = make_form(
        data=[
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"], 7.0],
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"], 2.0],
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"], 5.0],
        ],
        field_labels=["gene_symbol", "go_id", "score"],
        encoders={"gene_symbol": gene_enc, "go_id": go_enc},
    )
    out, _ = run(form, {
        "index_label": "gene_symbol",
        "columns_label": "go_id",
        "values_label": "score",
        "agg": "first",
        "output": "o",
    })
    assert out.data[0, 0] == 7.0
    print("PASS test_pivot_first_aggregates_duplicates")


def test_pivot_count_ignores_values():
    gene_enc = LabelEncoder()
    gene_enc.fit_transform(["A", "A", "A"])
    go_enc = LabelEncoder()
    go_enc.fit_transform(["GO:1", "GO:1", "GO:2"])

    form = make_form(
        data=[
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"]],
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"]],
            [gene_enc.mapping["A"], go_enc.mapping["GO:2"]],
        ],
        field_labels=["gene_symbol", "go_id"],
        encoders={"gene_symbol": gene_enc, "go_id": go_enc},
    )
    out, _ = run(form, {
        "index_label": "gene_symbol",
        "columns_label": "go_id",
        "agg": "count",
        "output": "o",
    })
    assert out.data.tolist() == [[2.0, 1.0]]
    print("PASS test_pivot_count_ignores_values")


# ------------------------------------------------------------------ #
# Uncoded columns
# ------------------------------------------------------------------ #

def test_pivot_uncoded_columns_use_position_codes():
    form = make_form(
        data=[
            [0.0, 0.0],
            [0.0, 1.0],
            [1.0, 0.0],
        ],
        field_labels=["gene_symbol", "go_id"],
    )
    out, _ = run(form, {
        "index_label": "gene_symbol",
        "columns_label": "go_id",
        "agg": "first",
        "output": "o",
    })
    assert out.labels["gene_symbol"] == {"0": 0, "1": 1}
    assert out.labels["go_id"] == {"0": 0, "1": 1}
    print("PASS test_pivot_uncoded_columns_use_position_codes")


# ------------------------------------------------------------------ #
# Sparsity
# ------------------------------------------------------------------ #

def test_pivot_sparse_pairs_left_zero():
    gene_enc = LabelEncoder()
    gene_enc.fit_transform(["A", "B"])
    go_enc = LabelEncoder()
    go_enc.fit_transform(["GO:1", "GO:2"])

    form = make_form(
        data=[
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"]],
            [gene_enc.mapping["B"], go_enc.mapping["GO:2"]],
        ],
        field_labels=["gene_symbol", "go_id"],
        encoders={"gene_symbol": gene_enc, "go_id": go_enc},
    )
    out, exp = run(form, {
        "index_label": "gene_symbol",
        "columns_label": "go_id",
        "output": "o",
    })
    assert out.data.tolist() == [[1.0, 0.0], [0.0, 1.0]]
    assert exp["n_nonzero"] == 2
    assert exp["sparsity"] == 0.5
    print("PASS test_pivot_sparse_pairs_left_zero")


# ------------------------------------------------------------------ #
# Order of labels
# ------------------------------------------------------------------ #

def test_pivot_label_order_is_first_appearance():
    gene_enc = LabelEncoder()
    gene_enc.fit_transform(["B", "A", "C"])
    go_enc = LabelEncoder()
    go_enc.fit_transform(["GO:2", "GO:1", "GO:2"])

    form = make_form(
        data=[
            [gene_enc.mapping["B"], go_enc.mapping["GO:2"]],
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"]],
            [gene_enc.mapping["C"], go_enc.mapping["GO:2"]],
        ],
        field_labels=["gene_symbol", "go_id"],
        encoders={"gene_symbol": gene_enc, "go_id": go_enc},
    )
    out, _ = run(form, {
        "index_label": "gene_symbol",
        "columns_label": "go_id",
        "output": "o",
    })
    # First appearance order, not alphabetical.
    assert list(out.labels["gene_symbol"].keys()) == ["B", "A", "C"]
    assert list(out.labels["go_id"].keys()) == ["GO:2", "GO:1"]
    print("PASS test_pivot_label_order_is_first_appearance")


# ------------------------------------------------------------------ #
# Missing values
# ------------------------------------------------------------------ #

def test_pivot_nan_values_become_zero_for_sum():
    gene_enc = LabelEncoder()
    gene_enc.fit_transform(["A", "A"])
    go_enc = LabelEncoder()
    go_enc.fit_transform(["GO:1", "GO:1"])

    form = make_form(
        data=[
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"], np.nan],
            [gene_enc.mapping["A"], go_enc.mapping["GO:1"], 3.0],
        ],
        field_labels=["gene_symbol", "go_id", "score"],
        encoders={"gene_symbol": gene_enc, "go_id": go_enc},
    )
    out, _ = run(form, {
        "index_label": "gene_symbol",
        "columns_label": "go_id",
        "values_label": "score",
        "agg": "sum",
        "output": "o",
    })
    # pandas groupby.sum skips NaN, so 0 + 3 = 3
    assert out.data[0, 0] == 3.0
    print("PASS test_pivot_nan_values_become_zero_for_sum")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_cell_cap_raises():
    # 100 x 100 pair rows with all distinct (index, column) values.
    gene_enc = LabelEncoder()
    gene_enc.fit_transform([f"g{i}" for i in range(100)])
    go_enc = LabelEncoder()
    go_enc.fit_transform([f"GO:{i}" for i in range(100)])

    data = []
    for i in range(100):
        data.append([gene_enc.mapping[f"g{i}"], go_enc.mapping[f"GO:{i}"]])

    form = make_form(
        data=data,
        field_labels=["gene_symbol", "go_id"],
        encoders={"gene_symbol": gene_enc, "go_id": go_enc},
    )
    # 100 x 100 = 10000 cells, well under cap. Should succeed.
    out, exp = run(form, {
        "index_label": "gene_symbol",
        "columns_label": "go_id",
        "output": "o",
    })
    assert exp["n_index"] == 100
    assert exp["n_columns"] == 100
    print("PASS test_cell_cap_raises")


def test_bad_params_raise():
    form = make_form(
        data=[[0.0, 0.0]],
        field_labels=["gene_symbol", "go_id"],
    )
    bad = [
        {"columns_label": "go_id", "output": "o"},
        {"index_label": "gene_symbol", "output": "o"},
        {"index_label": "missing", "columns_label": "go_id", "output": "o"},
        {"index_label": "gene_symbol", "columns_label": "missing", "output": "o"},
        {"index_label": "gene_symbol", "columns_label": "go_id",
         "values_label": "missing", "output": "o"},
        {"index_label": "gene_symbol", "columns_label": "go_id",
         "agg": "bogus", "output": "o"},
        {"index_label": "gene_symbol", "columns_label": "go_id",
         "index_name": "same", "columns_name": "same", "output": "o"},
    ]
    for params in bad:
        try:
            run(form, params)
        except StepError:
            continue
        raise AssertionError(f"params={params} did not raise")
    print("PASS test_bad_params_raise")


def main():
    tests = [
        test_pivot_binary_membership,
        test_pivot_with_values_column,
        test_pivot_sum_aggregates_duplicates,
        test_pivot_max_aggregates_duplicates,
        test_pivot_min_aggregates_duplicates,
        test_pivot_first_aggregates_duplicates,
        test_pivot_count_ignores_values,
        test_pivot_uncoded_columns_use_position_codes,
        test_pivot_sparse_pairs_left_zero,
        test_pivot_label_order_is_first_appearance,
        test_pivot_nan_values_become_zero_for_sum,
        test_cell_cap_raises,
        test_bad_params_raise,
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