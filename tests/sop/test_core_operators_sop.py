"""SOP numerical checks for core transforms against pandas/NumPy."""
from __future__ import annotations

import numpy as np
import pandas as pd
from biopipe_sdk.testing import run_operator
from src.core import Form


def form(data, sample_labels, feature_labels, info=None):
    return Form(
        data=np.asarray(data, dtype=np.float32),
        dims=["sample", "feature"],
        labels={"sample": {k: i for i, k in enumerate(sample_labels)},
                "feature": {k: i for i, k in enumerate(feature_labels)}},
        info={"missing_code": np.nan, **(info or {})},
    )


DATA = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float32)
SAMPLES = ["s0", "s1"]
FEATURES = ["f0", "f1", "f2"]


def test_select_matches_pandas():
    from src.task.step.steps.select import SelectStep
    out = run_operator(SelectStep,
                       [form(DATA, SAMPLES, FEATURES)],
                       {"dim": "sample", "labels": ["s1"]})
    assert list(out.labels["sample"]) == ["s1"]
    np.testing.assert_allclose(out.data, DATA[[1]])


def test_drop_matches_pandas():
    from src.task.step.steps.drop import DropStep
    out = run_operator(DropStep, [form(DATA, SAMPLES, FEATURES)],
                       {"dim": "feature", "labels": ["f1"]})
    assert list(out.labels["feature"]) == ["f0", "f2"]
    np.testing.assert_allclose(out.data, DATA[:, [0, 2]])


def test_rename_dim_preserves_values():
    from src.task.step.steps.rename_dim import RenameDimStep
    out = run_operator(RenameDimStep, [form(DATA, SAMPLES, FEATURES)],
                       {"from": "sample", "to": "cell"})
    assert out.dims == ["cell", "feature"]
    np.testing.assert_allclose(out.data, DATA)


def test_transpose_matches_numpy():
    from src.task.step.steps.transpose import TransposeStep
    out = run_operator(TransposeStep, [form(DATA, SAMPLES, FEATURES)],
                       {"order": ["feature", "sample"]})
    np.testing.assert_allclose(out.data, DATA.T)


def test_concat_matches_pandas():
    from src.task.step.steps.concat import ConcatStep
    left = form(DATA, SAMPLES, FEATURES)
    right = form(DATA + 10, ["s2", "s3"], FEATURES)
    out = run_operator(ConcatStep, [left, right], {"axis": "sample"})
    expected = np.vstack([DATA, DATA + 10])
    np.testing.assert_allclose(out.data, expected)
    assert list(out.labels["sample"]) == ["s0", "s1", "s2", "s3"]


def test_filter_min_matches_pandas():
    from src.task.step.steps.filter_min import FilterMinStep
    data = np.array([[0, 5, 0], [0, 0, 0]], dtype=np.float32)
    out = run_operator(FilterMinStep, [form(data, SAMPLES, FEATURES)],
                       {"dim": "feature", "min_value": 4, "min_samples": 1})
    expected = data[:, [1]]
    np.testing.assert_allclose(out.data, expected)
    assert list(out.labels["feature"]) == ["f1"]


def test_filter_by_matches_pandas():
    from src.task.step.steps.filter_by import FilterByStep
    data = form(DATA, SAMPLES, FEATURES)
    metrics = Form(
        data=np.array([[10.0], [1.0]], dtype=np.float32),
        dims=["sample", "statistic"],
        labels={"sample": {"s0": 0, "s1": 1}, "statistic": {"total": 0}},
        info={"missing_code": np.nan},
    )
    out = run_operator(FilterByStep, [data, metrics],
                       {"dim": "sample", "rules": [{"field": "total", "min": 5}]})
    np.testing.assert_allclose(out.data, DATA[[0]])


def test_normalize_cpm_matches_pandas():
    from src.task.step.steps.normalize import NormalizeStep
    out = run_operator(NormalizeStep, [form(DATA, SAMPLES, FEATURES)],
                       {"method": "cpm", "dim": "sample"})
    expected = DATA / DATA.sum(axis=1, keepdims=True) * 1_000_000
    np.testing.assert_allclose(out.data, expected, rtol=1e-6, atol=1e-4)


def test_log_transform_matches_numpy():
    from src.task.step.steps.log_transform import LogTransformStep
    out = run_operator(LogTransformStep, [form(DATA, SAMPLES, FEATURES)],
                       {"base": 2, "pseudocount": 1})
    np.testing.assert_allclose(out.data, np.log2(DATA + 1), rtol=1e-6, atol=1e-6)


def test_qc_metrics_matches_pandas():
    from src.task.step.steps.qc_metrics import QcMetricsStep
    feature_by_sample = Form(
        data=np.asarray(DATA.T, dtype=np.float32),
        dims=["feature", "sample"],
        labels={"feature": {k: i for i, k in enumerate(FEATURES)},
                "sample": {k: i for i, k in enumerate(SAMPLES)}},
        info={"missing_code": np.nan},
    )
    out = run_operator(QcMetricsStep, [feature_by_sample],
                       {"feature_dim": "feature", "sample_dim": "sample",
                        "metrics": [{"name": "total", "op": "sum"},
                                    {"name": "n_detected", "op": "nonzero"}]})
    totals = DATA.sum(axis=1)
    detected = (DATA != 0).sum(axis=1)
    np.testing.assert_allclose(out.data[:, out.labels["statistic"]["total"]], totals)
    np.testing.assert_allclose(out.data[:, out.labels["statistic"]["n_detected"]], detected)


def test_scale_features_matches_pandas():
    from src.task.step.steps.scale_features import ScaleFeaturesStep
    out = run_operator(ScaleFeaturesStep, [form(DATA, SAMPLES, FEATURES)],
                       {"dim": "sample"})
    frame = pd.DataFrame(DATA)
    expected = ((frame - frame.mean()) / frame.std(ddof=0)).to_numpy()
    np.testing.assert_allclose(out.data, expected, rtol=1e-5, atol=1e-5)
