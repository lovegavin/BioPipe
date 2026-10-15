import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.gene_structure import GeneStructureStep
from biopipe_sdk.testing import run_operator
from src.reader.readers._encoder import get_encoder


def _make_form(records):
    """records: (seqid, type, start, end, strand, gene_id)."""
    seqid_enc = get_encoder("labelencoder")
    type_enc = get_encoder("labelencoder")
    strand_enc = get_encoder("labelencoder")
    attr_enc = get_encoder("labelencoder")
    seqids = [r[0] for r in records]
    types = [r[1] for r in records]
    strands = [r[4] for r in records]
    attrs = [f"gene_id={r[5]}" if r[5] else "" for r in records]
    seqid_codes = seqid_enc.fit_transform(seqids)
    type_codes = type_enc.fit_transform(types)
    strand_codes = strand_enc.fit_transform(strands)
    attr_codes = attr_enc.fit_transform(attrs)
    starts = np.array([r[2] for r in records], dtype=np.float32)
    ends = np.array([r[3] for r in records], dtype=np.float32)
    data = np.column_stack([
        seqid_codes, type_codes, starts, ends, strand_codes, attr_codes,
    ]).astype(np.float32)
    field_labels = {"seqid": 0, "type": 1, "start": 2, "end": 3,
                    "strand": 4, "attributes": 5}
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
                "strand": strand_enc, "attributes": attr_enc,
            }},
        },
    )


def _row(out, gene_id):
    i = out.labels["gene"][gene_id]
    return {n: float(out.data[i, j])
            for j, n in enumerate(("n_exons", "n_introns", "gene_length",
                                   "cds_total", "strand"))}


def test_hand_counted_two_genes():
    # geneA: gene span 1..1000 (1000 bp), 3 exons, 3 CDS
    #   CDS 50..250   -> 201 bp
    #   CDS 400..600  -> 201 bp
    #   CDS 850..1000 -> 151 bp
    #   cds_total = 553
    # geneB: gene span 1..400 (400 bp), 1 exon, 1 CDS 1..400 -> 400 bp
    records = [
        ("chr1", "gene", 1,    1000, "+", "geneA"),
        ("chr1", "exon", 1,    300,  "+", "geneA"),
        ("chr1", "CDS",  50,   250,  "+", "geneA"),
        ("chr1", "exon", 400,  600,  "+", "geneA"),
        ("chr1", "CDS",  400,  600,  "+", "geneA"),
        ("chr1", "exon", 800,  1000, "+", "geneA"),
        ("chr1", "CDS",  850,  1000, "+", "geneA"),
        ("chr2", "gene", 1,    400,  "-", "geneB"),
        ("chr2", "exon", 1,    400,  "-", "geneB"),
        ("chr2", "CDS",  1,    400,  "-", "geneB"),
    ]
    out = run_operator(GeneStructureStep, [_make_form(records)], {})
    assert out.dims == ["gene", "statistic"]
    assert set(out.labels["gene"]) == {"geneA", "geneB"}
    assert out.labels["statistic"] == {
        "n_exons": 0, "n_introns": 1, "gene_length": 2,
        "cds_total": 3, "strand": 4,
    }

    a = _row(out, "geneA")
    assert a["n_exons"] == 3.0
    assert a["n_introns"] == 2.0
    assert a["gene_length"] == 1000.0
    assert a["cds_total"] == 553.0
    assert a["strand"] == 1.0

    b = _row(out, "geneB")
    assert b["n_exons"] == 1.0
    assert b["n_introns"] == 0.0
    assert b["gene_length"] == 400.0
    assert b["cds_total"] == 400.0
    assert b["strand"] == -1.0

    assert out.info["representation"] == "gene_structure"


def test_single_exon_gene_no_introns():
    records = [
        ("chr1", "gene", 10, 200, "+", "single"),
        ("chr1", "exon", 10, 200, "+", "single"),
        ("chr1", "CDS",  10, 200, "+", "single"),
    ]
    out = run_operator(GeneStructureStep, [_make_form(records)], {})
    r = _row(out, "single")
    assert r["n_exons"] == 1.0
    assert r["n_introns"] == 0.0
    assert r["gene_length"] == 191.0
    assert r["cds_total"] == 191.0


def test_no_genes_rejected():
    records = [("chr1", "exon", 1, 100, "+", "")]
    with pytest.raises(StepError, match="no 'gene' records"):
        run_operator(GeneStructureStep, [_make_form(records)], {})


def test_missing_strand_encoder_rejected():
    form = _make_form([("chr1", "gene", 1, 100, "+", "g")])
    form.info["encoders"]["field"].pop("strand")
    with pytest.raises(StepError, match="'strand' column is not encoded"):
        run_operator(GeneStructureStep, [form], {})
