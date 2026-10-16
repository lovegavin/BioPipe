"""Hand-counted verification for scale_features.

Runs with: python tasks/scale_features_demo/test_scale_features.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core import Form, StepError
from src.task.step.steps.scale_features import ScaleFeaturesStep
from biopipe_sdk.testing import run_operator


def _make_form(data, missing_code=np.nan):
    data = np.asarray(data, dtype=np.float32)
    n_f, n_s = data.shape
    return Form(
        data=data,
        dims=["feature", "sample"],
        labels={
            "feature": {f"f{i}": i for i in range(n_f)},
            "sample": {f"s{i}": i for i in range(n_s)},
        },
        info={"missing_code": missing_code},
    )


def test_scale_along_sample_axis():
    # f0 = [1, 2, 3]  mean 2, std sqrt(2/3) ~ 0.8165
    # f1 = [4, 5, 6]  mean 5, std sqrt(2/3)
    # expected z-scores: [-1.2247, 0, 1.2247] per row
    form = _make_form([[1, 2, 3], [4, 5, 6]])
    out = run_operator(ScaleFeaturesStep, [form], {"dim": "sample"})
    sd = np.sqrt(2.0 / 3.0)
    expected = np.array([
        [(1 - 2) / sd, (2 - 2) / sd, (3 - 2) / sd],
        [(4 - 5) / sd, (5 - 5) / sd, (6 - 5) / sd],
    ], dtype=np.float32)
    np.testing.assert_allclose(out.data, expected, atol=1e-6)
    assert out.dims == ["feature", "sample"]
    assert out.labels["feature"] == {"f0": 0, "f1": 1}
    assert out.labels["sample"] == {"s0": 0, "s1": 1, "s2": 2}
    assert out.info["representation"] == "scaled"
    print("  scale along sample              ok")


def test_scale_along_feature_axis():
    # s0 = [1, 4]  mean 2.5, std 1.5 -> [-1, 1]
    # s1 = [2, 5]  mean 3.5, std 1.5 -> [-1, 1]
    # s2 = [3, 6]  mean 4.5, std 1.5 -> [-1, 1]
    form = _make_form([[1, 2, 3], [4, 5, 6]])
    out = run_operator(ScaleFeaturesStep, [form], {"dim": "feature"})
    expected = np.array([
        [-1.0, -1.0, -1.0],
        [ 1.0,  1.0,  1.0],
    ], dtype=np.float32)
    np.testing.assert_allclose(out.data, expected, atol=1e-6)
    print("  scale along feature             ok")


def test_constant_row_becomes_zero():
    # f1 is constant along the sample axis -> mean subtraction leaves 0,
    # std is 0 and must not produce NaN.
    form = _make_form([[1, 2, 3], [5, 5, 5]])
    out = run_operator(ScaleFeaturesStep, [form], {"dim": "sample"})
    row1 = out.data[1]
    assert np.all(row1 == 0.0), row1
    print("  constant row -> 0               ok")


def test_nan_preserved():
    # f0 = [1, 2, nan] -> mean of valid (1, 2) = 1.5, std = 0.5
    # f1 = [4, 5, 6]   -> mean 5, std sqrt(2/3)
    form = _make_form([[1, 2, np.nan], [4, 5, 6]])
    out = run_operator(ScaleFeaturesStep, [form], {"dim": "sample"})
    assert np.isnan(out.data[0, 2])
    assert not np.isnan(out.data[0, 0])
    assert abs(out.data[0, 0] - (-1.0)) < 1e-6
    assert abs(out.data[0, 1] - ( 1.0)) < 1e-6
    print("  NaN preserved                   ok")


def test_numeric_missing_code_minus_9():
    # Same as previous, missing marked as -9 instead of NaN.
    form = _make_form([[1, 2, -9], [4, 5, 6]], missing_code=-9)
    out = run_operator(ScaleFeaturesStep, [form], {"dim": "sample"})
    assert np.isnan(out.data[0, 2])
    assert abs(out.data[0, 0] - (-1.0)) < 1e-6
    assert abs(out.data[0, 1] - ( 1.0)) < 1e-6
    assert out.info["missing_code"] is not None
    print("  numeric missing_code=-9         ok")


def test_max_value_clips():
    # f0 = [1, 5, 10] -> mean 16/3, std sqrt(162/9) ~ 4.24
    # z = [-1.023, 0.236, 1.259] with max_value=1 clip
    form = _make_form([[1, 5, 10]])
    out = run_operator(ScaleFeaturesStep, [form],
                       {"dim": "sample", "max_value": 1.0})
    assert out.data[0, 2] == 1.0
    assert out.data[0, 0] >= -1.0 and out.data[0, 0] < 0
    assert -1.0 <= out.data[0, 1] <= 1.0
    print("  max_value clip                  ok")


def test_zero_std_along_dim_is_not_nan():
    # Two features, each constant across three samples.
    form = _make_form([[3, 3, 3], [7, 7, 7]])
    out = run_operator(ScaleFeaturesStep, [form], {"dim": "sample"})
    assert np.all(out.data == 0.0)
    print("  zero std -> zeros not NaN       ok")


def test_encoder_and_genotype_semantics_cleared():
    # Form with representation="hard_call" and encoders must drop both
    # after scaling: the numeric values are no longer hard calls.
    form = _make_form([[0, 1, 2], [2, 1, 0]])
    form.info["representation"] = "hard_call"
    form.info["ploidy"] = 2
    form.info["encoders"] = {"feature": {"f0": object()}}
    out = run_operator(ScaleFeaturesStep, [form], {"dim": "sample"})
    assert out.info["representation"] == "scaled"
    assert "ploidy" not in out.info
    assert "encoders" not in out.info
    print("  semantics cleared on transform  ok")


def test_wrong_dim_rejected():
    form = _make_form([[1, 2, 3]])
    try:
        run_operator(ScaleFeaturesStep, [form], {"dim": "nonexistent"})
        raise AssertionError("expected dim rejection")
    except AssertionError:
        raise
    except StepError as exc:
        assert "nonexistent" in str(exc)
    print("  wrong dim rejected              ok")


def test_bad_max_value_rejected():
    form = _make_form([[1, 2, 3]])
    for bad in (0, -1):
        try:
            run_operator(ScaleFeaturesStep, [form],
                         {"dim": "sample", "max_value": bad})
            raise AssertionError("expected max_value rejection")
        except AssertionError:
            raise
        except StepError as exc:
            assert "max_value" in str(exc)
    print("  bad max_value rejected          ok")


def test_1d_input_rejected():
    form = Form(
        data=np.array([1.0, 2.0, 3.0], dtype=np.float32),
        dims=["x"],
        labels={"x": {"a": 0, "b": 1, "c": 2}},
        info={"missing_code": np.nan},
    )
    try:
        run_operator(ScaleFeaturesStep, [form], {"dim": "x"})
        raise AssertionError("expected 1D rejection")
    except AssertionError:
        raise
    except StepError as exc:
        # The input contract enforces ndim=2 and rejects 1D input
        # before the operator body runs. Both messages must be
        # accepted; the contract layer runs first.
        msg = str(exc)
        assert ("2D" in msg) or ("2 维" in msg), msg
    print("  1D input rejected               ok")


def main():
    print("scale_features verification")
    test_scale_along_sample_axis()
    test_scale_along_feature_axis()
    test_constant_row_becomes_zero()
    test_nan_preserved()
    test_numeric_missing_code_minus_9()
    test_max_value_clips()
    test_zero_std_along_dim_is_not_nan()
    test_encoder_and_genotype_semantics_cleared()
    test_wrong_dim_rejected()
    test_bad_max_value_rejected()
    test_1d_input_rejected()
    print()
    print("all checks passed")


if __name__ == "__main__":
    main()
