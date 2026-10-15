import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.gff_feature_stats import GffFeatureStatsStep
from biopipe_sdk.testing import run_operator
from src.reader.readers._encoder import get_encoder


def _make_form(records):
    """records: list of (seqid, type, start, end, strand)."""
    seqid_enc = get_encoder("labelencoder")
    type_enc = get_encoder("labelencoder")
    strand_enc = get_encoder("labelencoder")
    seqid_codes = seqid_enc.fit_transform([r[0] for r in records])
    type_codes = type_enc.fit_transform([r[1] for r in records])
    strand_codes = strand_enc.fit_transform([r[4] for r in records])
    starts = np.array([r[2] for r in records], dtype=np.float32)
    ends = np.array([r[3] for r in records], dtype=np.float32)
    data = np.column_stack([
        seqid_codes, type_codes, starts, ends, strand_codes,
    ]).astype(np.float32)
    n = len(records)
    return Form(
        data=data,
        dims=["record", "field"],
        labels={
            "record": {str(i): i for i in range(n)},
            "field": {"seqid": 0, "type": 1, "start": 2, "end": 3, "strand": 4},
        },
        info={
            "missing_code": np.nan,
            "encoders": {"field": {
                "seqid": seqid_enc, "type": type_enc, "strand": strand_enc,
            }},
        },
    )


def _make_form_without_type(records):
    """records: list of (seqid, start, end, strand). No 'type' column."""
    seqid_enc = get_encoder("labelencoder")
    strand_enc = get_encoder("labelencoder")
    seqid_codes = seqid_enc.fit_transform([r[0] for r in records])
    strand_codes = strand_enc.fit_transform([r[3] for r in records])
    starts = np.array([r[1] for r in records], dtype=np.float32)
    ends = np.array([r[2] for r in records], dtype=np.float32)
    data = np.column_stack([
        seqid_codes, starts, ends, strand_codes,
    ]).astype(np.float32)
    n = len(records)
    return Form(
        data=data,
        dims=["record", "field"],
        labels={
            "record": {str(i): i for i in range(n)},
            "field": {"seqid": 0, "start": 1, "end": 2, "strand": 3},
        },
        info={
            "missing_code": np.nan,
            "encoders": {"field": {
                "seqid": seqid_enc, "strand": strand_enc,
            }},
        },
    )


def _row(out, ftype):
    i = out.labels["feature_type"][ftype]
    return {n: float(out.data[i, j])
            for j, n in enumerate(("count", "total_length", "mean_length",
                                   "min_length", "max_length",
                                   "mean_exons_per_gene"))}


def test_hand_counted_2_genes_3_exons():
    # gene lengths: 500, 300     -> total 800, mean 400, min 300, max 500
    # exon lengths: 100, 100, 50 -> total 250, mean 83.333, min 50, max 100
    # mean_exons_per_gene = 3/2 = 1.5
    records = [
        ("chr1", "gene", 1,    500,  "+"),
        ("chr1", "gene", 1000, 1299, "-"),
        ("chr1", "exon", 1,    100,  "+"),
        ("chr1", "exon", 200,  299,  "+"),
        ("chr1", "exon", 1000, 1049, "-"),
    ]
    out = run_operator(GffFeatureStatsStep, [_make_form(records)], {})
    assert out.dims == ["feature_type", "statistic"]
    assert set(out.labels["feature_type"]) == {"gene", "exon"}
    assert out.labels["statistic"] == {
        "count": 0, "total_length": 1, "mean_length": 2,
        "min_length": 3, "max_length": 4, "mean_exons_per_gene": 5,
    }

    g = _row(out, "gene")
    assert np.isclose(g["count"], 2.0)
    assert np.isclose(g["total_length"], 800.0)
    assert np.isclose(g["mean_length"], 400.0)
    assert np.isclose(g["min_length"], 300.0)
    assert np.isclose(g["max_length"], 500.0)
    assert np.isclose(g["mean_exons_per_gene"], 1.5)

    e = _row(out, "exon")
    assert np.isclose(e["count"], 3.0)
    assert np.isclose(e["total_length"], 250.0)
    assert np.isclose(e["mean_length"], 250.0 / 3.0)
    assert np.isclose(e["min_length"], 50.0)
    assert np.isclose(e["max_length"], 100.0)
    assert np.isclose(e["mean_exons_per_gene"], 0.0)

    assert out.info["representation"] == "gff_feature_stats"


def test_no_exon_records():
    # Only genes: mean_exons_per_gene must be 0.
    records = [
        ("chr1", "gene", 1,   100, "+"),
        ("chr1", "gene", 500, 700, "+"),
    ]
    out = run_operator(GffFeatureStatsStep, [_make_form(records)], {})
    g = _row(out, "gene")
    assert np.isclose(g["count"], 2.0)
    assert np.isclose(g["mean_exons_per_gene"], 0.0)


def test_only_exons_no_gene():
    # mean_exons_per_gene stays 0 when there are no gene records.
    records = [
        ("chr1", "exon", 1,   50, "+"),
        ("chr1", "exon", 100, 200, "-"),
    ]
    out = run_operator(GffFeatureStatsStep, [_make_form(records)], {})
    e = _row(out, "exon")
    assert np.isclose(e["count"], 2.0)
    assert np.isclose(e["mean_exons_per_gene"], 0.0)


def test_missing_type_label_rejected():
    form = _make_form_without_type([("chr1", 1, 100, "+")])
    with pytest.raises(StepError, match="no 'type' label"):
        run_operator(GffFeatureStatsStep, [form], {})


def test_unnamed_type_encoder_rejected():
    form = _make_form([("chr1", "gene", 1, 100, "+")])
    form.info["encoders"]["field"].pop("type")
    with pytest.raises(StepError, match="not encoded"):
        run_operator(GffFeatureStatsStep, [form], {})
