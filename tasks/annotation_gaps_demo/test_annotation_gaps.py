import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.annotation_gaps import AnnotationGapsStep
from biopipe_sdk.testing import run_operator
from src.reader.readers._encoder import get_encoder


def _make_form(records):
    """records: (seqid, type, start, end)."""
    seqid_enc = get_encoder("labelencoder")
    type_enc = get_encoder("labelencoder")
    seqid_codes = seqid_enc.fit_transform([r[0] for r in records])
    type_codes = type_enc.fit_transform([r[1] for r in records])
    starts = np.array([r[2] for r in records], dtype=np.float32)
    ends = np.array([r[3] for r in records], dtype=np.float32)
    data = np.column_stack([
        seqid_codes, type_codes, starts, ends,
    ]).astype(np.float32)
    field_labels = {"seqid": 0, "type": 1, "start": 2, "end": 3}
    n = len(records)
    return Form(
        data=data,
        dims=["record", "field"],
        labels={
            "record": {str(i): i for i in range(n)},
            "field": field_labels,
        },
        info={
            "missing_code": np.nan,
            "encoders": {"field": {
                "seqid": seqid_enc, "type": type_enc,
            }},
        },
    )


def _row(out, i):
    return {n: float(out.data[i, j])
            for j, n in enumerate(("gap_length", "left_start", "left_end",
                                   "right_start", "right_end"))}


def test_hand_counted_gaps():
    # chr1: genes at 1-100, 200-300, 1000-1100
    #       gaps: 99 (100+1..199), 699 (300+1..999)
    # chr2: genes at 1-50, 100-200
    #       gap: 49 (50+1..99)
    records = [
        ("chr1", "gene", 1,    100,  ),
        ("chr1", "gene", 200,  300,  ),
        ("chr1", "gene", 1000, 1100, ),
        ("chr2", "gene", 1,    50,   ),
        ("chr2", "gene", 100,  200,  ),
    ]
    out = run_operator(AnnotationGapsStep, [_make_form(records)], {})
    assert out.dims == ["gap", "statistic"]
    assert out.data.shape == (3, 5)
    assert out.labels["statistic"] == {
        "gap_length": 0, "left_start": 1, "left_end": 2,
        "right_start": 3, "right_end": 4,
    }
    assert out.info["seqid"] == ["chr1", "chr1", "chr2"]
    assert out.info["left_gene"] == ["chr1:1-100", "chr1:200-300",
                                     "chr2:1-50"]
    assert out.info["right_gene"] == ["chr1:200-300", "chr1:1000-1100",
                                      "chr2:100-200"]

    r0 = _row(out, 0)
    assert r0["gap_length"] == 99.0
    assert r0["left_start"] == 1.0
    assert r0["left_end"] == 100.0
    assert r0["right_start"] == 200.0
    assert r0["right_end"] == 300.0

    r1 = _row(out, 1)
    assert r1["gap_length"] == 699.0
    assert r1["left_start"] == 200.0
    assert r1["left_end"] == 300.0
    assert r1["right_start"] == 1000.0
    assert r1["right_end"] == 1100.0

    r2 = _row(out, 2)
    assert r2["gap_length"] == 49.0
    assert r2["left_start"] == 1.0
    assert r2["left_end"] == 50.0
    assert r2["right_start"] == 100.0
    assert r2["right_end"] == 200.0

    assert out.info["representation"] == "annotation_gaps"


def test_min_gap_filters():
    records = [
        ("chr1", "gene", 1,   100, ),
        ("chr1", "gene", 110, 200, ),  # gap = 9
        ("chr1", "gene", 500, 600, ),  # gap = 299
    ]
    out = run_operator(
        AnnotationGapsStep, [_make_form(records)], {"min_gap": 100},
    )
    assert out.data.shape == (1, 5)
    assert _row(out, 0)["gap_length"] == 299.0
    assert out.info["seqid"] == ["chr1"]


def test_overlapping_genes_skipped():
    # chr1: gene 1-200, gene 150-300 (overlap)
    #       then gene 1000-1100 (gap 699 from the second)
    # Only the 699 gap must appear.
    records = [
        ("chr1", "gene", 1,    200,  ),
        ("chr1", "gene", 150,  300,  ),
        ("chr1", "gene", 1000, 1100, ),
    ]
    out = run_operator(AnnotationGapsStep, [_make_form(records)], {})
    assert out.data.shape == (1, 5)
    assert _row(out, 0)["gap_length"] == 699.0
    assert out.info["left_gene"] == ["chr1:150-300"]


def test_single_gene_no_gaps():
    records = [("chr1", "gene", 1, 100)]
    out = run_operator(AnnotationGapsStep, [_make_form(records)], {})
    assert out.data.shape == (0, 5)
    assert out.info["seqid"] == []


def test_non_gene_records_ignored():
    # Only genes produce gaps; exons between genes are not considered.
    records = [
        ("chr1", "gene", 1,   100),
        ("chr1", "exon", 150, 200),
        ("chr1", "gene", 500, 600),
    ]
    out = run_operator(AnnotationGapsStep, [_make_form(records)], {})
    assert out.data.shape == (1, 5)
    assert _row(out, 0)["gap_length"] == 399.0


def test_no_genes_rejected():
    records = [("chr1", "exon", 1, 100)]
    with pytest.raises(StepError, match="no 'gene' records"):
        run_operator(AnnotationGapsStep, [_make_form(records)], {})


def test_missing_seqid_encoder_rejected():
    form = _make_form([("chr1", "gene", 1, 100)])
    form.info["encoders"]["field"].pop("seqid")
    with pytest.raises(StepError, match="'seqid' column is not encoded"):
        run_operator(AnnotationGapsStep, [form], {})
