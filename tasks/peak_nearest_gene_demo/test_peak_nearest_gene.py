import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.peak_nearest_gene import PeakNearestGeneStep
from biopipe_sdk.testing import run_operator
from src.reader.readers._encoder import get_encoder


def _make_peaks(records):
    """records: (chrom, start, end). chrom is a string like 'chr1'."""
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


def _make_genes(records, encoded_chrom=True, include_type=True):
    """records: (seqid, start, end, strand, gene_id).

    encoded_chrom=True  -> seqid stored as encoder codes (like BED chrom)
    encoded_chrom=False -> seqid stored as raw numbers (like GFF3 '22')
    """
    seqids = [r[0] for r in records]
    strands = [r[3] for r in records]
    attrs = [f"gene_id={r[4]}" for r in records]

    if encoded_chrom:
        chrom_enc = get_encoder("labelencoder")
        chrom_codes = chrom_enc.fit_transform(seqids)
    else:
        chrom_enc = None
        chrom_codes = np.array([float(s) for s in seqids], dtype=np.float32)

    strand_enc = get_encoder("labelencoder")
    attr_enc = get_encoder("labelencoder")

    columns = [
        chrom_codes,
        np.array([r[1] for r in records], dtype=np.float32),
        np.array([r[2] for r in records], dtype=np.float32),
        strand_enc.fit_transform(strands),
        attr_enc.fit_transform(attrs),
    ]
    field_labels = {"seqid": 0, "start": 1, "end": 2,
                    "strand": 3, "attributes": 4}
    encoders_for_field = {"strand": strand_enc, "attributes": attr_enc}
    if chrom_enc is not None:
        encoders_for_field["seqid"] = chrom_enc

    if include_type:
        type_enc = get_encoder("labelencoder")
        columns.append(type_enc.fit_transform(["gene"] * len(records)))
        field_labels["type"] = 5
        encoders_for_field["type"] = type_enc

    data = np.column_stack(columns).astype(np.float32)
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
            "encoders": {"field": encoders_for_field},
        },
    )


def _row(out, i):
    return {n: float(out.data[i, j])
            for j, n in enumerate(("distance", "gene_start", "gene_end",
                                   "gene_length", "strand"))}


def test_peak_inside_gene_distance_zero():
    peaks = _make_peaks([("chr1", 500, 600)])
    genes = _make_genes([("chr1", 100, 1000, "+", "geneA")])
    out = run_operator(PeakNearestGeneStep, [peaks, genes],
                       {"feature_type": "gene"})
    assert out.data.shape == (1, 5)
    assert out.info["gene_id"] == ["geneA"]
    assert out.info["chrom"] == ["chr1"]
    r = _row(out, 0)
    assert r["distance"] == 0.0
    assert r["gene_start"] == 100.0
    assert r["gene_end"] == 1000.0
    assert r["gene_length"] == 900.0
    assert r["strand"] == 1.0
    assert out.info["representation"] == "peak_nearest_gene"


def test_peak_right_of_gene():
    peaks = _make_peaks([("chr1", 2000, 2100)])
    genes = _make_genes([("chr1", 100, 500, "-", "geneA")])
    out = run_operator(PeakNearestGeneStep, [peaks, genes],
                       {"feature_type": "gene"})
    r = _row(out, 0)
    assert r["distance"] == 1500.0
    assert r["strand"] == -1.0


def test_peak_left_of_gene():
    peaks = _make_peaks([("chr1", 10, 50)])
    genes = _make_genes([("chr1", 1000, 2000, "+", "geneA")])
    out = run_operator(PeakNearestGeneStep, [peaks, genes],
                       {"feature_type": "gene"})
    r = _row(out, 0)
    assert r["distance"] == 950.0


def test_two_genes_picks_nearest():
    peaks = _make_peaks([("chr1", 5000, 5100)])
    genes = _make_genes([
        ("chr1", 100, 500, "+", "geneA"),
        ("chr1", 5200, 6000, "-", "geneB"),
    ])
    out = run_operator(PeakNearestGeneStep, [peaks, genes],
                       {"feature_type": "gene"})
    assert out.info["gene_id"] == ["geneB"]
    r = _row(out, 0)
    assert r["distance"] == 100.0
    assert r["strand"] == -1.0


def test_chrom_prefix_normalisation_encoded_on_a_only():
    # peaks use "chr1" (encoded), genes use "1" (raw numeric) -> match
    peaks = _make_peaks([("chr1", 500, 600)])
    genes = _make_genes(
        [("1", 100, 1000, "+", "geneA")], encoded_chrom=False,
    )
    out = run_operator(PeakNearestGeneStep, [peaks, genes],
                       {"feature_type": "gene"})
    assert out.info["gene_id"] == ["geneA"]
    assert out.info["chrom"] == ["chr1"]
    r = _row(out, 0)
    assert r["distance"] == 0.0


def test_chrom_prefix_normalisation_encoded_on_both():
    # peaks "chr1", genes "1" but genes' seqid was encoded as string
    peaks = _make_peaks([("chr1", 500, 600)])
    genes = _make_genes([("1", 100, 1000, "+", "geneA")],
                        encoded_chrom=True)
    out = run_operator(PeakNearestGeneStep, [peaks, genes],
                       {"feature_type": "gene"})
    assert out.info["gene_id"] == ["geneA"]
    assert out.info["chrom"] == ["chr1"]


def test_unmatched_chromosome_skipped():
    peaks = _make_peaks([("chr1", 500, 600)])
    genes = _make_genes([("chr2", 100, 1000, "+", "geneA")])
    out = run_operator(PeakNearestGeneStep, [peaks, genes],
                       {"feature_type": "gene"})
    assert out.data.shape == (0, 5)
    assert out.info["gene_id"] == []


def test_max_distance_filter():
    peaks = _make_peaks([("chr1", 5000, 5100)])
    genes = _make_genes([("chr1", 100, 500, "+", "geneA")])
    out = run_operator(PeakNearestGeneStep, [peaks, genes],
                       {"feature_type": "gene", "max_distance": 1000})
    assert out.data.shape == (0, 5)

    out2 = run_operator(PeakNearestGeneStep, [peaks, genes],
                        {"feature_type": "gene", "max_distance": 5000})
    assert out2.data.shape == (1, 5)


def test_no_type_column_rejected_when_filter_requested():
    peaks = _make_peaks([("chr1", 500, 600)])
    genes = _make_genes([("chr1", 100, 1000, "+", "geneA")],
                        include_type=False)
    with pytest.raises(StepError, match="no 'type' label"):
        run_operator(PeakNearestGeneStep, [peaks, genes],
                     {"feature_type": "gene"})


def test_feature_type_filter_picks_gene_only():
    peaks = _make_peaks([("chr1", 500, 600)])
    genes = _make_genes([("chr1", 100, 1000, "+", "geneA")],
                        include_type=True)
    out = run_operator(PeakNearestGeneStep, [peaks, genes],
                       {"feature_type": "gene"})
    assert out.data.shape == (1, 5)


def test_end_before_start_rejected():
    peaks = _make_peaks([("chr1", 500, 400)])
    genes = _make_genes([("chr1", 100, 1000, "+", "geneA")])
    with pytest.raises(StepError, match="end must be > start"):
        run_operator(PeakNearestGeneStep, [peaks, genes],
                     {"feature_type": "gene"})
