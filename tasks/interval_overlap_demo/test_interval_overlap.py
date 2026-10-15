import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.interval_overlap import IntervalOverlapStep
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
            for j, n in enumerate(("overlap_start", "overlap_end",
                                   "overlap_length", "a_length", "b_length",
                                   "overlap_fraction_a",
                                   "overlap_fraction_b"))}


def _sort_rows(out):
    """Return list of (a_id, b_id, row) sorted by a_id then b_id."""
    items = []
    for i in range(out.data.shape[0]):
        items.append((out.info["a_id"][i], out.info["b_id"][i], _row(out, i)))
    items.sort(key=lambda x: (x[0], x[1]))
    return items


def test_basic_overlap_pair():
    # A: chr1 [100,200)   B: chr1 [150,300)  -> overlap [150,200), length 50
    a = _make_form([("chr1", 100, 200)])
    b = _make_form([("chr1", 150, 300)])
    out = run_operator(IntervalOverlapStep, [a, b], {})
    assert out.dims == ["pair", "statistic"]
    assert out.data.shape == (1, 7)
    assert out.info["chrom"] == ["chr1"]
    assert out.info["representation"] == "interval_overlaps"

    r = _row(out, 0)
    assert r["overlap_start"] == 150.0
    assert r["overlap_end"] == 200.0
    assert r["overlap_length"] == 50.0
    assert r["a_length"] == 100.0
    assert r["b_length"] == 150.0
    assert np.isclose(r["overlap_fraction_a"], 0.5)
    assert np.isclose(r["overlap_fraction_b"], 50.0 / 150.0)


def test_no_overlap_no_rows():
    a = _make_form([("chr1", 100, 200)])
    b = _make_form([("chr1", 300, 400)])
    out = run_operator(IntervalOverlapStep, [a, b], {})
    assert out.data.shape == (0, 7)
    assert out.info["chrom"] == []
    assert out.info["representation"] == "interval_overlaps"


def test_touching_intervals_do_not_overlap():
    # [100,200) and [200,300): half-open, no overlap.
    a = _make_form([("chr1", 100, 200)])
    b = _make_form([("chr1", 200, 300)])
    out = run_operator(IntervalOverlapStep, [a, b], {})
    assert out.data.shape == (0, 7)


def test_one_a_overlaps_two_b():
    # A: chr1 [100,400)
    # B: chr1 [150,200), [300,500)
    # -> pairs (A0,B0) len 50, (A0,B1) len 100
    a = _make_form([("chr1", 100, 400)])
    b = _make_form([("chr1", 150, 200), ("chr1", 300, 500)])
    out = run_operator(IntervalOverlapStep, [a, b], {})
    assert out.data.shape == (2, 7)
    rows = _sort_rows(out)
    r0 = rows[0][2]
    r1 = rows[1][2]
    assert r0["overlap_length"] == 50.0
    assert r0["overlap_start"] == 150.0
    assert r0["overlap_end"] == 200.0
    assert r1["overlap_length"] == 100.0
    assert r1["overlap_start"] == 300.0
    assert r1["overlap_end"] == 400.0


def test_cross_chromosome_no_pairs():
    # Same start/end but different chrom -> no pair.
    a = _make_form([("chr1", 100, 200)])
    b = _make_form([("chr2", 100, 200)])
    out = run_operator(IntervalOverlapStep, [a, b], {})
    assert out.data.shape == (0, 7)


def test_min_overlap_filters_short_pairs():
    # A: chr1 [100,110) (10 bp)   B: chr1 [105,120)
    # overlap = 5 bp. min_overlap=6 rejects it, min_overlap=5 keeps it.
    a = _make_form([("chr1", 100, 110)])
    b = _make_form([("chr1", 105, 120)])
    out5 = run_operator(IntervalOverlapStep, [a, b], {"min_overlap": 5})
    assert out5.data.shape == (1, 7)
    r = _row(out5, 0)
    assert r["overlap_length"] == 5.0

    out6 = run_operator(IntervalOverlapStep, [a, b], {"min_overlap": 6})
    assert out6.data.shape == (0, 7)


def test_chain_multi_chromosome():
    # chr1: A0 [100,200), A1 [150,250); B0 [120,180)
    #   -> pairs (A0,B0) 60bp, (A1,B0) 30bp  -> 2 pairs on chr1
    # chr2: A2 [10,50); B1 [20,40)
    #   -> pair (A2,B1) 20bp                   -> 1 pair on chr2
    a = _make_form([
        ("chr1", 100, 200),
        ("chr1", 150, 250),
        ("chr2", 10, 50),
    ])
    b = _make_form([
        ("chr1", 120, 180),
        ("chr2", 20, 40),
    ])
    out = run_operator(IntervalOverlapStep, [a, b], {})
    assert out.data.shape == (3, 7)
    assert sorted(out.info["chrom"]) == ["chr1", "chr1", "chr2"]
    lengths = sorted(out.data[:, 2].tolist())
    assert lengths == [20.0, 30.0, 60.0]


def test_max_output_aborts():
    a = _make_form([("chr1", 0, 1000)])
    b = _make_form([("chr1", i, i + 1) for i in range(10)])
    with pytest.raises(StepError, match="exceeded max_output"):
        run_operator(IntervalOverlapStep, [a, b], {"max_output": 5})


def test_end_before_start_rejected():
    a = _make_form([("chr1", 200, 100)])
    b = _make_form([("chr1", 100, 200)])
    with pytest.raises(StepError, match="end must be > start"):
        run_operator(IntervalOverlapStep, [a, b], {})


def test_missing_chrom_encoder_rejected():
    a = _make_form([("chr1", 100, 200)])
    b = _make_form([("chr1", 100, 200)])
    b.info["encoders"]["field"].pop("chrom")
    with pytest.raises(StepError, match="'chrom' column is not encoded"):
        run_operator(IntervalOverlapStep, [a, b], {})
