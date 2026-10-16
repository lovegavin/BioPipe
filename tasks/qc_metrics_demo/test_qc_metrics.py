"""Hand-counted verification for qc_metrics.

Runs with: python tasks/qc_metrics_demo/test_qc_metrics.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core import Form, StepError
from src.task.step.steps.qc_metrics import QcMetricsStep
from biopipe_sdk.testing import run_operator


def _make_form(feature_names, data, missing_code=np.nan):
    data = np.asarray(data, dtype=np.float32)
    n_f, n_s = data.shape
    return Form(
        data=data,
        dims=["feature", "sample"],
        labels={
            "feature": {name: i for i, name in enumerate(feature_names)},
            "sample": {f"s{i}": i for i in range(n_s)},
        },
        info={"missing_code": missing_code},
    )


def _col(out, metric):
    j = out.labels["statistic"][metric]
    return out.data[:, j].tolist()


def test_sum_per_sample():
    # 3 features x 3 samples
    # col0 = 1+4+7 = 12
    # col1 = 2+5+8 = 15
    # col2 = 3+6+9 = 18
    form = _make_form(
        ["f0", "f1", "f2"],
        [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
    )
    out = run_operator(QcMetricsStep, [form],
                       {"metrics": [{"name": "total", "op": "sum"}]})
    assert out.dims == ["sample", "statistic"]
    assert out.labels["statistic"] == {"total": 0}
    assert _col(out, "total") == [12.0, 15.0, 18.0]
    assert out.info["representation"] == "qc_metrics"
    print("  sum per sample                  ok")


def test_nonzero_and_count():
    # nonzero counts non-missing and non-zero entries per column
    # col0 = [1, 0, 0]    -> 1 nonzero
    # col1 = [0, 0, 8]    -> 1 nonzero
    # col2 = [3, 6, 9]    -> 3 nonzero
    # count counts non-missing entries per column
    # all entries non-missing -> count = 3 for each column
    form = _make_form(
        ["f0", "f1", "f2"],
        [[1, 0, 3], [0, 0, 6], [0, 8, 9]],
    )
    out = run_operator(QcMetricsStep, [form], {
        "metrics": [
            {"name": "nz", "op": "nonzero"},
            {"name": "n_called", "op": "count"},
        ],
    })
    assert _col(out, "nz") == [1.0, 1.0, 3.0]
    assert _col(out, "n_called") == [3.0, 3.0, 3.0]
    print("  nonzero and count               ok")


def test_sum_and_count_with_nan():
    # col0 = [1, 4]   -> sum 5, count 2
    # col1 = [nan, 5] -> sum 5, count 1
    # col2 = [3, 6]   -> sum 9, count 2
    form = _make_form(
        ["f0", "f1"],
        [[1, np.nan, 3], [4, 5, 6]],
    )
    out = run_operator(QcMetricsStep, [form], {
        "metrics": [
            {"name": "total", "op": "sum"},
            {"name": "n_called", "op": "count"},
        ],
    })
    assert _col(out, "total") == [5.0, 5.0, 9.0]
    assert _col(out, "n_called") == [2.0, 1.0, 2.0]
    print("  sum/count with NaN              ok")


def test_mean_std_min_max():
    # col0 = [1, 3, 5] -> mean 3, std sqrt(8/3), min 1, max 5
    # col1 = [2, 4, 6] -> mean 4, std sqrt(8/3), min 2, max 6
    form = _make_form(
        ["f0", "f1", "f2"],
        [[1, 2], [3, 4], [5, 6]],
    )
    out = run_operator(QcMetricsStep, [form], {
        "metrics": [
            {"name": "mean", "op": "mean"},
            {"name": "std",  "op": "std"},
            {"name": "min",  "op": "min"},
            {"name": "max",  "op": "max"},
        ],
    })
    assert _col(out, "mean") == [3.0, 4.0]
    for v in _col(out, "std"):
        assert abs(v - np.sqrt(8.0 / 3.0)) < 1e-6
    assert _col(out, "min") == [1.0, 2.0]
    assert _col(out, "max") == [5.0, 6.0]
    print("  mean/std/min/max                ok")


def test_feature_pattern():
    # 4 features: 2 match "MT-", 2 do not.
    # col0: MT sum = 1 + 3 = 4
    # col1: MT sum = 2 + 4 = 6
    form = _make_form(
        ["MT-ND1", "MT-CO1", "GAPDH", "ACTB"],
        [[1, 2], [3, 4], [10, 20], [30, 40]],
    )
    out = run_operator(QcMetricsStep, [form],
                       {"metrics": [
                           {"name": "mt", "op": "sum",
                            "feature_pattern": "MT-"},
                       ]})
    assert _col(out, "mt") == [4.0, 6.0]
    print("  feature_pattern filtering       ok")


def test_divide_by():
    # total per column: [44, 66]
    # mt    per column: [4, 6]
    # pct = mt / total = [4/44, 6/66] = [0.0909..., 0.0909...]
    form = _make_form(
        ["MT-ND1", "MT-CO1", "GAPDH", "ACTB"],
        [[1, 2], [3, 4], [10, 20], [30, 40]],
    )
    out = run_operator(QcMetricsStep, [form], {
        "metrics": [
            {"name": "total", "op": "sum"},
            {"name": "mt", "op": "sum", "feature_pattern": "MT-"},
            {"name": "pct", "op": "sum", "feature_pattern": "MT-",
             "divide_by": "total"},
        ],
    })
    expected = 4.0 / 44.0
    assert abs(_col(out, "pct")[0] - expected) < 1e-6
    assert abs(_col(out, "pct")[1] - expected) < 1e-6
    print("  divide_by                       ok")


def test_numeric_missing_code():
    # missing marked as -9 instead of NaN
    # col0 = [1, -9]   -> sum 1, count 1
    # col1 = [2, 3]    -> sum 5, count 2
    form = _make_form(
        ["f0", "f1"],
        [[1, 2], [-9, 3]],
        missing_code=-9,
    )
    out = run_operator(QcMetricsStep, [form], {
        "metrics": [
            {"name": "total", "op": "sum"},
            {"name": "n_called", "op": "count"},
        ],
    })
    assert _col(out, "total") == [1.0, 5.0]
    assert _col(out, "n_called") == [1.0, 2.0]
    print("  numeric missing_code=-9         ok")


def test_pattern_matches_nothing():
    form = _make_form(["f0", "f1"], [[1, 2], [3, 4]])
    try:
        run_operator(QcMetricsStep, [form],
                     {"metrics": [
                         {"name": "x", "op": "sum",
                          "feature_pattern": "MT-"},
                     ]})
        raise AssertionError("expected pattern-no-match rejection")
    except AssertionError:
        raise
    except StepError as exc:
        assert "matched no feature" in str(exc)
    print("  empty pattern rejected          ok")


def test_divide_by_unknown():
    form = _make_form(["f0"], [[1, 2]])
    try:
        run_operator(QcMetricsStep, [form],
                     {"metrics": [
                         {"name": "x", "op": "sum",
                          "divide_by": "missing"},
                     ]})
        raise AssertionError("expected divide_by rejection")
    except AssertionError:
        raise
    except StepError as exc:
        assert "divide_by" in str(exc)
    print("  unknown divide_by rejected      ok")


def test_duplicate_names_rejected():
    form = _make_form(["f0"], [[1, 2]])
    try:
        run_operator(QcMetricsStep, [form],
                     {"metrics": [
                         {"name": "x", "op": "sum"},
                         {"name": "x", "op": "mean"},
                     ]})
        raise AssertionError("expected duplicate-name rejection")
    except AssertionError:
        raise
    except StepError as exc:
        assert "unique" in str(exc)
    print("  duplicate names rejected        ok")


def test_wrong_dim_order_rejected():
    # Valid Form, but transposed axes: [sample, feature] not [feature, sample]
    form = Form(
        data=np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float32),
        dims=["sample", "feature"],
        labels={
            "sample": {"s0": 0, "s1": 1},
            "feature": {"f0": 0, "f1": 1, "f2": 2},
        },
        info={"missing_code": np.nan},
    )
    try:
        run_operator(QcMetricsStep, [form],
                     {"metrics": [{"name": "x", "op": "sum"}]})
        raise AssertionError("expected dim-order rejection")
    except AssertionError:
        raise
    except StepError as exc:
        assert "expected 2D" in str(exc)
    print("  wrong dim order rejected        ok")


def main():
    print("qc_metrics verification")
    test_sum_per_sample()
    test_nonzero_and_count()
    test_sum_and_count_with_nan()
    test_mean_std_min_max()
    test_feature_pattern()
    test_divide_by()
    test_numeric_missing_code()
    test_pattern_matches_nothing()
    test_divide_by_unknown()
    test_duplicate_names_rejected()
    test_wrong_dim_order_rejected()
    print()
    print("all checks passed")


if __name__ == "__main__":
    main()
