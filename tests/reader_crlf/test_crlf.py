"""Verify every text reader handles CRLF and blank lines identically to LF.

Each test writes the same logical content twice (LF and CRLF), reads
both, and asserts the Form is byte-identical: same shape, same data,
same labels, same info. Only readers that were patched for CRLF are
tested here.
"""
from pathlib import Path

import numpy as np
import pytest

from src.reader import read_source


# ---------------------------------------------------------------- BED

BED_LINES = [
    "chr1\t100\t200\tpeak_a\t10\t+",
    "chr1\t300\t400\tpeak_b\t20\t-",
    "chr2\t500\t600\tpeak_c\t30\t+",
]


def _write(tmp_path, name, lines, newline):
    path = tmp_path / name
    path.write_bytes(newline.join(lines).encode("ascii") + newline.encode("ascii"))
    return path


def test_bed_crlf_matches_lf(tmp_path):
    lf = _write(tmp_path, "a.bed", BED_LINES, "\n")
    crlf = _write(tmp_path, "b.bed", BED_LINES, "\r\n")
    flf = read_source(lf, ["region", "field"],
                      {"region": "auto", "field": "builtin"})
    fcrlf = read_source(crlf, ["region", "field"],
                        {"region": "auto", "field": "builtin"})
    np.testing.assert_array_equal(flf.data, fcrlf.data)
    assert flf.dims == fcrlf.dims
    assert flf.labels["field"] == fcrlf.labels["field"]
    assert flf.data.shape == (3, 6)
    # chromEnd must be 200.0 in both, not "200\r" -> NaN
    assert fcrlf.data[0, 2] == 200.0
    assert fcrlf.data[2, 2] == 600.0
    # chrom code for row 2 must be a valid encoder value
    assert not np.isnan(fcrlf.data[2, 0])


def test_bed_crlf_with_blank_lines(tmp_path):
    lines = [
        "chr1\t100\t200\tpeak_a\t10\t+",
        "",
        "   ",
        "chr1\t300\t400\tpeak_b\t20\t-",
    ]
    path = _write(tmp_path, "blank.bed", lines, "\r\n")
    form = read_source(path, ["region", "field"],
                       {"region": "auto", "field": "builtin"})
    assert form.data.shape == (2, 6)
    assert form.data[0, 2] == 200.0
    assert form.data[1, 2] == 400.0


def test_bed_track_line_crlf(tmp_path):
    lines = [
        "track name=peaks description=\"demo\"",
        "browser position chr1:1-1000",
        "chr1\t100\t200\tpeak_a\t10\t+",
    ]
    path = _write(tmp_path, "track.bed", lines, "\r\n")
    form = read_source(path, ["region", "field"],
                       {"region": "auto", "field": "builtin"})
    assert form.data.shape == (1, 6)
    assert form.data[0, 1] == 100.0
    assert form.data[0, 2] == 200.0


def test_bed_data_row_starting_with_tracking_not_skipped(tmp_path):
    # A name field could begin with "tracking"; it must not be treated
    # as a track header line.
    lines = [
        "chr1\t100\t200\ttracking_region\t10\t+",
        "chr1\t300\t400\tpeak_b\t20\t-",
    ]
    path = _write(tmp_path, "tracking.bed", lines, "\r\n")
    form = read_source(path, ["region", "field"],
                       {"region": "auto", "field": "builtin"})
    assert form.data.shape == (2, 6)


# --------------------------------------------------------------- FASTA

FASTA_CONTENT = [
    ">seqA first",
    "ACGTACGT",
    ">seqB second",
    "TTTT",
]


def test_fasta_crlf_matches_lf(tmp_path):
    lf = _write(tmp_path, "a.fasta", FASTA_CONTENT, "\n")
    crlf = _write(tmp_path, "b.fasta", FASTA_CONTENT, "\r\n")
    flf = read_source(lf, ["sequence", "position"],
                      {"sequence": "builtin", "position": "auto"})
    fcrlf = read_source(crlf, ["sequence", "position"],
                        {"sequence": "builtin", "position": "auto"})
    np.testing.assert_array_equal(flf.data, fcrlf.data)
    assert flf.labels["sequence"] == fcrlf.labels["sequence"]
    assert flf.info["alphabet"] == fcrlf.info["alphabet"] == "dna"
    # seqA: A=0 C=1 G=2 T=3 A=0 C=1 G=2 T=3, seqB padded with NaN
    assert fcrlf.data[0, 0] == 0.0
    assert fcrlf.data[0, 1] == 1.0
    assert np.isnan(fcrlf.data[1, 4])


def test_fasta_crlf_with_blank_line_between_records(tmp_path):
    lines = [
        ">seqA",
        "ACGT",
        "",
        ">seqB",
        "TTTT",
    ]
    path = _write(tmp_path, "blank.fasta", lines, "\r\n")
    form = read_source(path, ["sequence", "position"],
                       {"sequence": "builtin", "position": "auto"})
    assert form.data.shape == (2, 4)
    assert form.data[0, 3] == 3.0
    assert form.data[1, 0] == 3.0


# --------------------------------------------------------------- GFF3

GFF3_LINES = [
    "##gff-version 3",
    "chr1\tsrc\tgene\t1\t500\t.\t+\t.\tID=geneA",
    "chr1\tsrc\texon\t1\t100\t.\t+\t.\tParent=geneA",
    "chr1\tsrc\texon\t200\t500\t.\t+\t.\tParent=geneA",
]


def test_gff3_crlf_matches_lf(tmp_path):
    lf = _write(tmp_path, "a.gff3", GFF3_LINES, "\n")
    crlf = _write(tmp_path, "b.gff3", GFF3_LINES, "\r\n")
    flf = read_source(lf, ["record", "field"],
                      {"record": "auto", "field": "builtin"})
    fcrlf = read_source(crlf, ["record", "field"],
                        {"record": "auto", "field": "builtin"})
    np.testing.assert_array_equal(flf.data, fcrlf.data)
    assert flf.data.shape == (3, 9)
    assert flf.labels["field"] == fcrlf.labels["field"]
    # start column is numeric
    assert fcrlf.data[0, 3] == 1.0
    assert fcrlf.data[2, 3] == 200.0
    assert fcrlf.data[2, 4] == 500.0


# --------------------------------------------------------------- GTF

GTF_LINES = [
    "# comment line",
    "chr1\tsrc\tgene\t100\t500\t.\t+\t.\tgene_id \"gA\";",
    "chr1\tsrc\texon\t100\t200\t.\t+\t.\tgene_id \"gA\";",
]


def test_gtf_crlf_matches_lf(tmp_path):
    lf = _write(tmp_path, "a.gtf", GTF_LINES, "\n")
    crlf = _write(tmp_path, "b.gtf", GTF_LINES, "\r\n")
    flf = read_source(lf, ["record", "field"],
                      {"record": "auto", "field": "builtin"})
    fcrlf = read_source(crlf, ["record", "field"],
                        {"record": "auto", "field": "builtin"})
    np.testing.assert_array_equal(flf.data, fcrlf.data)
    assert fcrlf.data.shape == (2, 9)
    assert fcrlf.data[0, 3] == 100.0
    assert fcrlf.data[1, 4] == 200.0


# --------------------------------------------------------------- GAF

# GAF requires exactly 17 columns. Build one minimal valid record plus
# a synonym so info["db_object_synonym"] is populated.
def _gaf_row(symbol, synonym="syn1|syn2"):
    return "\t".join([
        "UniProt", "P12345", symbol, "enables",
        "GO:0000001", "PMID:1", "IDA", "UniProt:P1",
        "F", "protein name", synonym, "protein",
        "taxon:9606", "20240101", "UniProt", "", "",
    ])


def test_gaf_crlf_matches_lf(tmp_path):
    lines = ["!gaf-version: 2.2", _gaf_row("GENE_A"), _gaf_row("GENE_B")]
    lf = _write(tmp_path, "a.gaf", lines, "\n")
    crlf = _write(tmp_path, "b.gaf", lines, "\r\n")
    flf = read_source(lf, ["annotation", "field"],
                      {"annotation": "auto", "field": "builtin"})
    fcrlf = read_source(crlf, ["annotation", "field"],
                        {"annotation": "auto", "field": "builtin"})
    np.testing.assert_array_equal(flf.data, fcrlf.data)
    assert flf.data.shape[0] == 2
    assert flf.labels["field"] == fcrlf.labels["field"]


# --------------------------------------------------------------- VCF

VCF_LINES = [
    "##fileformat=VCFv4.2",
    "##contig=<ID=chr1>",
    "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\tS2",
    "chr1\t100\t.\tA\tG\t.\t.\t.\tGT\t0/1\t0/0",
    "chr1\t200\trs1\tA\tT,C\t.\t.\t.\tGT\t1/2\t0/0",
]


def test_vcf_crlf_matches_lf(tmp_path):
    lf = _write(tmp_path, "a.vcf", VCF_LINES, "\n")
    crlf = _write(tmp_path, "b.vcf", VCF_LINES, "\r\n")
    flf = read_source(lf, ["variant", "sample"],
                      {"variant": "builtin", "sample": "builtin"})
    fcrlf = read_source(crlf, ["variant", "sample"],
                        {"variant": "builtin", "sample": "builtin"})
    np.testing.assert_array_equal(flf.data, fcrlf.data)
    assert flf.info["representation"] == "hard_call"
    assert flf.info["ploidy"] == fcrlf.info["ploidy"] == 2
    # chr1:100 has a real record -> row 0
    # chr1:200 has 2 ALTs -> 2 rows
    assert fcrlf.data.shape == (3, 2)
    # ALT count for S1 at chr1:100 with 0/1 -> 1
    assert fcrlf.data[0, 0] == 1.0
    # ALT count for S2 at chr1:100 with 0/0 -> 0
    assert fcrlf.data[0, 1] == 0.0


# --------------------------------------------------------------- MTX

def test_mtx_crlf_matches_lf(tmp_path):
    # MatrixMarket coordinate file, 2x2, plus barcodes/features siblings.
    mtx_lines = [
        "%%MatrixMarket matrix coordinate real general",
        "% comment",
        "2 2 3",
        "1 1 1.0",
        "1 2 2.0",
        "2 2 3.0",
    ]
    barcodes_lines = ["cellA", "cellB"]
    features_lines = ["geneX\tX\tGeneX", "geneY\tY\tGeneY"]

    lf = tmp_path / "lf"
    crlf = tmp_path / "crlf"
    lf.mkdir()
    crlf.mkdir()

    _write(lf, "matrix.mtx", mtx_lines, "\n")
    _write(crlf, "matrix.mtx", mtx_lines, "\r\n")
    _write(lf, "barcodes.tsv", barcodes_lines, "\n")
    _write(crlf, "barcodes.tsv", barcodes_lines, "\r\n")
    _write(lf, "features.tsv", features_lines, "\n")
    _write(crlf, "features.tsv", features_lines, "\r\n")

    flf = read_source(lf / "matrix.mtx", ["gene", "cell"],
                      {"gene": "builtin", "cell": "builtin"})
    fcrlf = read_source(crlf / "matrix.mtx", ["gene", "cell"],
                        {"gene": "builtin", "cell": "builtin"})
    np.testing.assert_array_equal(flf.data, fcrlf.data)
    assert flf.labels["gene"] == fcrlf.labels["gene"]
    assert flf.labels["cell"] == fcrlf.labels["cell"]
    assert fcrlf.data.shape == (2, 2)
    assert fcrlf.data[0, 0] == 1.0
    assert fcrlf.data[0, 1] == 2.0
    assert fcrlf.data[1, 1] == 3.0
    assert fcrlf.data[1, 0] == 0.0
