import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.interval_merge import IntervalMergeStep
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


def _row(out, i):
    return {n: float(out.data[i, j])
            for j, n in enumerate(("start", "end", "length", "n_intervals"))}


def test_two_overlapping_one_separate():
    # chr1 [100,200) + chr1 [150,300) -> chr1 [100,300) n=2
    # chr1 [500,600)                  -> chr1 [500,600) n=1
    records = [
        ("chr1", 100, 200),
        ("chr1", 150, 300),
        ("chr1", 500, 600),
    ]
    out = run_operator(IntervalMergeStep, [_make_form(records)], {})
    assert out.dims == ["merged_region", "statistic"]
    assert out.data.shape == (2, 4)
    assert out.labels["statistic"] == {
        "start": 0, "end": 1, "length": 2, "n_intervals": 3,
    }
    assert out.info["chrom"] == ["chr1", "chr1"]
    assert out.info["representation"] == "merged_intervals"

    r0 = _row(out, 0)
    assert r0["start"] == 100.0
    assert r0["end"] == 300.0
    assert r0["length"] == 200.0
    assert r0["n_intervals"] == 2.0

    r1 = _row(out, 1)
    assert r1["start"] == 500.0
    assert r1["end"] == 600.0
    assert r1["length"] == 100.0
    assert r1["n_intervals"] == 1.0


def test_bookended_merged_with_min_overlap_zero():
    # chr1 [100,200) + chr1 [200,300): gap = 0 -> merged (bedtools default).
    records = [
        ("chr1", 100, 200),
        ("chr1", 200, 300),
    ]
    out = run_operator(IntervalMergeStep, [_make_form(records)], {})
    assert out.data.shape == (1, 4)
    r = _row(out, 0)
    assert r["start"] == 100.0
    assert r["end"] == 300.0
    assert r["n_intervals"] == 2.0


def test_min_overlap_bridges_gap():
    # chr1 [100,200) and chr1 [205,300): gap = 5.
    # min_overlap=4 -> no merge; min_overlap=5 -> merge.
    records = [("chr1", 100, 200), ("chr1", 205, 300)]

    out0 = run_operator(IntervalMergeStep, [_make_form(records)],
                        {"min_overlap": 4})
    assert out0.data.shape == (2, 4)

    out5 = run_operator(IntervalMergeStep, [_make_form(records)],
                        {"min_overlap": 5})
    assert out5.data.shape == (1, 4)
    assert _row(out5, 0)["end"] == 300.0
    assert _row(out5, 0)["n_intervals"] == 2.0


def test_multi_chromosome():
    # chr1: [100,200), [150,250)        -> 1 merged, n=2
    # chr2: [1,50),   [100,150)         -> 2 merged, n=1 each
    records = [
        ("chr1", 100, 200),
        ("chr1", 150, 250),
        ("chr2", 1, 50),
        ("chr2", 100, 150),
    ]
    out = run_operator(IntervalMergeStep, [_make_form(records)], {})
    assert out.data.shape == (3, 4)
    # Sorted by chromosome, then start within each chromosome.
    assert out.info["chrom"] == ["chr1", "chr2", "chr2"]

    r0 = _row(out, 0)
    assert r0["start"] == 100.0 and r0["end"] == 250.0 and r0["n_intervals"] == 2.0

    r1 = _row(out, 1)
    assert r1["start"] == 1.0 and r1["end"] == 50.0 and r1["n_intervals"] == 1.0

    r2 = _row(out, 2)
    assert r2["start"] == 100.0 and r2["end"] == 150.0 and r2["n_intervals"] == 1.0


def test_three_intervals_chain_merge():
    # [100,200), [150,250), [240,400) all overlap in a chain -> one region.
    records = [
        ("chr1", 100, 200),
        ("chr1", 150, 250),
        ("chr1", 240, 400),
    ]
    out = run_operator(IntervalMergeStep, [_make_form(records)], {})
    assert out.data.shape == (1, 4)
    r = _row(out, 0)
    assert r["start"] == 100.0
    assert r["end"] == 400.0
    assert r["length"] == 300.0
    assert r["n_intervals"] == 3.0


def test_end_before_start_rejected():
    records = [("chr1", 200, 100)]
    with pytest.raises(StepError, match="end must be > start"):
        run_operator(IntervalMergeStep, [_make_form(records)], {})


def test_missing_chrom_encoder_rejected():
    form = _make_form([("chr1", 100, 200)])
    form.info["encoders"]["field"].pop("chrom")
    with pytest.raises(StepError, match="'chrom' column is not encoded"):
        run_operator(IntervalMergeStep, [form], {})
