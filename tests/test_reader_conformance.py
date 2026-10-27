"""Reader conformance for standard-format edge cases that are easy to miss."""
from __future__ import annotations

import numpy as np

from src.reader import read_source


def _read(path, dims, labels):
    return read_source(path, dims, labels)


def test_gff3_stops_before_embedded_fasta(tmp_path):
    path = tmp_path / "annot.gff3"
    path.write_text(
        "##gff-version 3\n"
        "chr1\tsrc\tgene\t1\t10\t.\t+\t.\tID=gene1\n"
        "##FASTA\n"
        ">chr1\n"
        "ACGTACGTACGT\n",
        encoding="utf-8",
    )
    form = _read(path, ["record", "field"], {"record": "auto", "field": "builtin"})
    assert form.data.shape == (1, 9)
    assert "gene" in form.info["encoders"]["field"]["type"].inverse.values()


def test_gtf_stops_before_embedded_fasta(tmp_path):
    path = tmp_path / "annot.gtf"
    path.write_text(
        'chr1\tsrc\tgene\t1\t10\t.\t+\t.\tgene_id "gene1";\n'
        "##FASTA\n"
        ">chr1\n"
        "ACGTACGTACGT\n",
        encoding="utf-8",
    )
    form = _read(path, ["record", "field"], {"record": "auto", "field": "builtin"})
    assert form.data.shape == (1, 9)


def test_bed_skips_comments_and_preserves_spaces_in_tab_fields(tmp_path):
    path = tmp_path / "peaks.bed"
    path.write_text(
        "# a comment line that is not a BED record\n"
        "chr1\t100\t200\tname with spaces\t0\t+\n",
        encoding="utf-8",
    )
    form = _read(path, ["region", "field"], {"region": "auto", "field": "builtin"})
    assert form.data.shape == (1, 6)
    name_col = form.labels["field"]["name"]
    encoder = form.info["encoders"]["field"]["name"]
    assert encoder.inverse[int(form.data[0, name_col])] == "name with spaces"


def test_bed_accepts_plain_whitespace_when_tabs_are_absent(tmp_path):
    path = tmp_path / "legacy.bed"
    path.write_text("chr1 100 200\n", encoding="utf-8")
    form = _read(path, ["region", "field"], {"region": "auto", "field": "builtin"})
    assert form.data.shape == (1, 3)
    assert form.data[0, form.labels["field"]["chromStart"]] == 100
    assert form.data[0, form.labels["field"]["chromEnd"]] == 200


def test_fasta_keeps_empty_records_aligned(tmp_path):
    path = tmp_path / "records.fasta"
    path.write_text(">empty\n>filled\nACGT\n", encoding="utf-8")
    form = _read(path, ["sequence", "position"], {"sequence": "builtin", "position": "auto"})
    assert form.data.shape == (2, 4)
    assert list(form.labels["sequence"]) == ["empty", "filled"]
    assert np.isnan(form.data[0]).all()
    assert form.data[1, 0] == 0  # A


def test_fasta_rejects_sequence_before_header(tmp_path):
    path = tmp_path / "bad.fasta"
    path.write_text("ACGT\n>seq\nACGT\n", encoding="utf-8")
    try:
        _read(path, ["sequence", "position"], {"sequence": "builtin", "position": "auto"})
    except Exception as exc:
        assert "before" in str(exc)
    else:
        raise AssertionError("expected a ReaderError")


def test_fasta_alphabet_inference_handles_protein_unknowns(tmp_path):
    path = tmp_path / "protein.faa"
    path.write_text(">p\nMKXW\n", encoding="utf-8")
    form = _read(path, ["sequence", "position"], {"sequence": "builtin", "position": "auto"})
    assert form.info["alphabet"] == "protein"
