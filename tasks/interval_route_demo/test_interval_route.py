"""Standalone verification of the interval analysis route.

Run with: python tasks/interval_route_demo/test_interval_route.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core import Form, StepError
from src.reader import read_source
from src.reader.readers._encoder import get_encoder
from src.task.step.steps.interval_stats import IntervalStatsStep
from src.task.step.steps.interval_merge import IntervalMergeStep
from src.task.step.steps.interval_overlap import IntervalOverlapStep
from biopipe_sdk.testing import run_operator


CCRE = Path(__file__).parent / "input" / "cCREs.bed"


def _make_intervals(records):
    chrom_enc = get_encoder("labelencoder")
    chroms = chrom_enc.fit_transform([r[0] for r in records])
    starts = np.array([r[1] for r in records], dtype=np.float32)
    ends = np.array([r[2] for r in records], dtype=np.float32)
    data = np.column_stack([chroms, starts, ends]).astype(np.float32)
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


def _stat_row(out, i):
    return {name: float(out.data[i, j])
            for j, name in enumerate(out.labels["statistic"])}


def test_interval_stats_hand_counted():
    # chr1: 100-200 (length = 100), 300-400 (length = 100)
    # chr2: 50-149 (length = 99)
    records = [
        ("chr1", 100, 200),
        ("chr1", 300, 400),
        ("chr2", 50, 149),
    ]
    form = _make_intervals(records)
    out = run_operator(IntervalStatsStep, [form], {})
    stats = {lbl: _stat_row(out, pos)
             for lbl, pos in out.labels["chrom"].items()}
    assert stats["chr1"]["n_intervals"] == 2.0
    assert stats["chr1"]["total_bp"] == 200.0
    assert stats["chr1"]["mean_length"] == 100.0
    assert stats["chr1"]["median_length"] == 100.0
    assert stats["chr1"]["min_length"] == 100.0
    assert stats["chr1"]["max_length"] == 100.0
    assert stats["chr1"]["span_bp"] == 300.0
    assert stats["chr2"]["n_intervals"] == 1.0
    assert stats["chr2"]["total_bp"] == 99.0
    assert stats["chr2"]["min_length"] == 99.0
    assert stats["chr2"]["max_length"] == 99.0
    print("  interval_stats hand-counted          ok")


def test_interval_merge_hand_counted():
    # chr1: 100-200 and 150-250 overlap -> merged 100-250 (length 150)
    # chr1: 300-400 -> 300-400 (length 100)
    # chr2: 50-149 -> 50-149 (length 99)
    records = [
        ("chr1", 100, 200),
        ("chr1", 150, 250),
        ("chr1", 300, 400),
        ("chr2", 50, 149),
    ]
    form = _make_intervals(records)
    out = run_operator(IntervalMergeStep, [form], {"min_overlap": 0})
    lengths = sorted(float(out.data[i, out.labels["statistic"]["length"]])
                     for i in range(out.data.shape[0]))
    assert lengths == [99.0, 100.0, 150.0], lengths
    print("  interval_merge hand-counted          ok")


def test_interval_overlap_hand_counted():
    # A: chr1 100-200, B: chr1 150-300 -> overlap 150-200 = length 50
    a = _make_intervals([("chr1", 100, 200)])
    b = _make_intervals([("chr1", 150, 300)])
    out = run_operator(IntervalOverlapStep, [a, b], {"min_overlap": 1})
    assert out.data.shape[0] == 1
    row = {name: float(out.data[0, j])
           for j, name in enumerate(out.labels["statistic"])}
    assert row["overlap_start"] == 150.0
    assert row["overlap_end"] == 200.0
    assert row["overlap_length"] == 50.0
    assert row["a_length"] == 100.0
    assert row["b_length"] == 150.0
    assert abs(row["overlap_fraction_a"] - 0.5) < 1e-6
    print("  interval_overlap hand-counted        ok")


def test_interval_overlap_min_overlap_filters():
    # A: chr1 100-110 (length 10). B: chr1 105-120 -> overlap = 5
    a = _make_intervals([("chr1", 100, 110)])
    b = _make_intervals([("chr1", 105, 120)])
    out = run_operator(IntervalOverlapStep, [a, b], {"min_overlap": 10})
    assert out.data.shape[0] == 0
    out2 = run_operator(IntervalOverlapStep, [a, b], {"min_overlap": 1})
    assert out2.data.shape[0] == 1
    assert float(out2.data[0, out2.labels["statistic"]["overlap_length"]]) == 5.0
    print("  interval_overlap min_overlap         ok")


def test_real_ccre_count():
    if not CCRE.exists():
        print("  real cCRE count (data missing)       skip")
        return
    form = read_source(
        CCRE, dims=["region", "field"],
        labels={"region": "auto", "field": "builtin"},
    )
    out = run_operator(IntervalStatsStep, [form], {})
    stat = out.labels["statistic"]
    total = sum(float(out.data[i, stat["n_intervals"]])
                for i in range(out.data.shape[0]))
    assert int(total) == 1063878, f"cCRE count {total} != 1063878"
    print(f"  real cCRE count == 1063878           ok")


def test_wrong_dim_rejected():
    form = _make_intervals([("chr1", 100, 200)])
    bad = Form(
        data=form.data[:, :1],
        dims=form.dims,
        labels={"region": form.labels["region"],
                "field": {"chrom": 0}},
        info={"missing_code": np.nan,
              "encoders": {"field": {"chrom": form.info["encoders"]["field"]["chrom"]}}},
    )
    try:
        run_operator(IntervalStatsStep, [bad], {})
        raise AssertionError("expected rejection")
    except AssertionError:
        raise
    except StepError:
        pass
    print("  missing coordinate columns rejected  ok")


def main():
    print("interval route verification")
    test_interval_stats_hand_counted()
    test_interval_merge_hand_counted()
    test_interval_overlap_hand_counted()
    test_interval_overlap_min_overlap_filters()
    test_real_ccre_count()
    test_wrong_dim_rejected()
    print()
    print("all checks passed")


if __name__ == "__main__":
    main()
