import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.interval_stats import IntervalStatsStep
from biopipe_sdk.testing import run_operator
from src.reader.readers._encoder import get_encoder


def _make_form(records):
    """records: (chrom, start, end)."""
    chrom_enc = get_encoder("labelencoder")
    chrom_codes = chrom_enc.fit_transform([r[0] for r in records])
    starts = np.array([r[1] for r in records], dtype=np.float32)
    ends = np.array([r[2] for r in records], dtype=np.float32)
    data = np.column_stack([chrom_codes, starts, ends]).astype(np.float32)
    n = len(records)
    return Form(
        data=data,
        dims=["region", "field"],
        labels={
            "region": {str(i): i for i in range(n)},
            "field": {"chrom": 0, "chromStart": 1, "chromEnd": 2},
        },
        info={
            "missing_code": np.nan,
            "encoders": {"field": {"chrom": chrom_enc}},
        },
    )


def _make_form_no_end(records):
    """records: (chrom, start). Field axis has chrom + chromStart only."""
    chrom_enc = get_encoder("labelencoder")
    chrom_codes = chrom_enc.fit_transform([r[0] for r in records])
    starts = np.array([r[1] for r in records], dtype=np.float32)
    data = np.column_stack([chrom_codes, starts]).astype(np.float32)
    n = len(records)
    return Form(
        data=data,
        dims=["region", "field"],
        labels={
            "region": {str(i): i for i in range(n)},
            "field": {"chrom": 0, "chromStart": 1},
        },
        info={
            "missing_code": np.nan,
            "encoders": {"field": {"chrom": chrom_enc}},
        },
    )


def _row(out, chrom):
    i = out.labels["chrom"][chrom]
    return {n: float(out.data[i, j])
            for j, n in enumerate(("n_intervals", "total_bp", "mean_length",
                                   "median_length", "min_length",
                                   "max_length", "span_bp"))}


def test_hand_counted_three_chroms():
    # chr1: [100,200) len=100, [300,500) len=200, [1000,1100) len=100
    #   n=3, total=400, mean=133.333..., median=100, min=100, max=200
    #   span = 1100 - 100 = 1000
    # chr2: [10,60) len=50
    #   n=1, total=50, mean=50, median=50, min=50, max=50, span=50
    # chr3: [1,11) len=10, [20,40) len=20
    #   n=2, total=30, mean=15, median=15, min=10, max=20, span=39
    records = [
        ("chr1", 100,  200),
        ("chr1", 300,  500),
        ("chr1", 1000, 1100),
        ("chr2", 10,   60),
        ("chr3", 1,    11),
        ("chr3", 20,   40),
    ]
    out = run_operator(IntervalStatsStep, [_make_form(records)], {})
    assert out.dims == ["chrom", "statistic"]
    assert out.labels["chrom"] == {"chr1": 0, "chr2": 1, "chr3": 2}
    assert out.labels["statistic"] == {
        "n_intervals": 0, "total_bp": 1, "mean_length": 2,
        "median_length": 3, "min_length": 4, "max_length": 5, "span_bp": 6,
    }

    r1 = _row(out, "chr1")
    assert r1["n_intervals"] == 3.0
    assert r1["total_bp"] == 400.0
    assert np.isclose(r1["mean_length"], 400.0 / 3.0)
    assert r1["median_length"] == 100.0
    assert r1["min_length"] == 100.0
    assert r1["max_length"] == 200.0
    assert r1["span_bp"] == 1000.0

    r2 = _row(out, "chr2")
    assert r2["n_intervals"] == 1.0
    assert r2["total_bp"] == 50.0
    assert r2["mean_length"] == 50.0
    assert r2["median_length"] == 50.0
    assert r2["span_bp"] == 50.0

    r3 = _row(out, "chr3")
    assert r3["n_intervals"] == 2.0
    assert r3["total_bp"] == 30.0
    assert r3["mean_length"] == 15.0
    assert r3["median_length"] == 15.0
    assert r3["min_length"] == 10.0
    assert r3["max_length"] == 20.0
    assert r3["span_bp"] == 39.0

    assert out.info["representation"] == "interval_stats"


def test_even_count_median_is_average_of_middle_two():
    # chr1: lengths 10, 20, 30, 40 -> median = (20 + 30) / 2 = 25
    records = [
        ("chr1", 0,   10),
        ("chr1", 100, 120),
        ("chr1", 200, 230),
        ("chr1", 300, 340),
    ]
    out = run_operator(IntervalStatsStep, [_make_form(records)], {})
    r = _row(out, "chr1")
    assert r["n_intervals"] == 4.0
    assert r["median_length"] == 25.0
    assert r["total_bp"] == 100.0


def test_single_interval():
    records = [("chr1", 100, 200)]
    out = run_operator(IntervalStatsStep, [_make_form(records)], {})
    assert out.data.shape == (1, 7)
    r = _row(out, "chr1")
    assert r["n_intervals"] == 1.0
    assert r["total_bp"] == 100.0
    assert r["mean_length"] == 100.0
    assert r["median_length"] == 100.0
    assert r["min_length"] == 100.0
    assert r["max_length"] == 100.0
    assert r["span_bp"] == 100.0


def test_end_before_start_rejected():
    records = [("chr1", 200, 100)]
    with pytest.raises(StepError, match="end must be > start"):
        run_operator(IntervalStatsStep, [_make_form(records)], {})


def test_missing_chrom_encoder_rejected():
    form = _make_form([("chr1", 100, 200)])
    form.info["encoders"]["field"].pop("chrom")
    with pytest.raises(StepError, match="'chrom' column is not encoded"):
        run_operator(IntervalStatsStep, [form], {})


def test_missing_end_label_rejected():
    form = _make_form_no_end([("chr1", 100)])
    with pytest.raises(StepError, match="no 'chromEnd' label"):
        run_operator(IntervalStatsStep, [form], {})
