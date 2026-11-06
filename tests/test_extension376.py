"""Tests for gene-level counting, normalisation and bias operators."""
from __future__ import annotations

import gzip
import struct

import numpy as np
import pytest

from src.core import FileArtifact, Form, StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.context import Context
from src.task.step.steps._count_utils import FeatureIndex, count_alignments, read_gff_features
from src.task.step.steps.bam_gene_bias import BamGeneBiasStep
from src.task.step.steps.bam_gene_counts import BamGeneCountsStep
from src.task.step.steps.counts_normalize import CountsNormalizeStep

_SEQ_CODES = "=ACMGRSVTWYHKDBN"
_CIGAR_OPS = "MIDNSHP=X"
_FIELDS = ("seqid", "source", "type", "start", "end", "score", "strand", "phase", "attributes")
_ENCODED = ("seqid", "source", "type", "strand", "attributes")


def _write_bam(tmp_path, references, records, name="tiny.bam"):
    header = b"BAM\x01" + struct.pack("<i", 0) + struct.pack("<i", len(references))
    for reference, length in references:
        encoded = reference.encode() + b"\x00"
        header += struct.pack("<i", len(encoded)) + encoded + struct.pack("<i", length)
    body = b""
    for flag, mapq, ref_id, pos, cigar, sequence in records:
        read_name = b"r\x00"
        cigar_bytes = b"".join(
            struct.pack("<I", (length << 4) | _CIGAR_OPS.index(operation))
            for operation, length in cigar)
        packed = struct.pack(
            "<iiBBHHHiiii", ref_id, pos, len(read_name), mapq, 0, len(cigar),
            flag, len(sequence), -1, -1, 0)
        payload = packed + read_name + cigar_bytes + bytes([40]) * len(sequence)
        body += struct.pack("<i", len(payload)) + payload
    path = tmp_path / name
    with gzip.open(path, "wb") as handle:
        handle.write(header + body)
    return str(path)


def _write_gff(tmp_path, rows, name="genes.gff"):
    lines = ["##gff-version 3"]
    for seqid, start, end, gene_id in rows:
        lines.append(f"{seqid}\tsrc\tgene\t{start}\t{end}\t.\t+\t.\tID={gene_id};locus_tag={gene_id}")
    path = tmp_path / name
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))
    return str(path)


def _gff_form(rows):
    columns = {name: [] for name in _FIELDS}
    for seqid, start, end, gene_id in rows:
        columns["seqid"].append(seqid)
        columns["source"].append("src")
        columns["type"].append("gene")
        columns["start"].append(start)
        columns["end"].append(end)
        columns["score"].append(0.0)
        columns["strand"].append("+")
        columns["phase"].append(0)
        columns["attributes"].append(f"ID={gene_id};locus_tag={gene_id}")
    encoders = {name: LabelEncoder() for name in _ENCODED}
    codes = {name: encoders[name].fit_transform(columns[name]) for name in _ENCODED}
    data = np.zeros((len(rows), len(_FIELDS)), dtype=np.float64)
    for index in range(len(rows)):
        for column, name in enumerate(_FIELDS):
            data[index, column] = codes[name][index] if name in codes else columns[name][index]
    return Form(data, ["feature", "field"],
                {"feature": {str(i): i for i in range(len(rows))},
                 "field": {name: i for i, name in enumerate(_FIELDS)}},
                info={"encoders": {"field": encoders}})


def _run(step, params, inputs, tmp_path):
    if getattr(step, "name", None) in (None, "", "unnamed"):
        step.name = step.definition["id"]
    ctx = Context(tmp_path / "task", {})
    ctx.step_params = dict(params)
    step.run(ctx, inputs)
    return step.export(ctx)


def test_read_gff_features_zero_based(tmp_path):
    path = _write_gff(tmp_path, [("chr1", 11, 20, "g1"), ("chr2", 1, 5, "g2")])
    features = read_gff_features(path, "gene", "locus_tag")
    assert features == [("chr1", "g1", 10, 20, "+"), ("chr2", "g2", 0, 5, "+")]


def test_feature_index_deduplicates():
    index = FeatureIndex([("chr1", "g1", 0, 20, "+")], bin_size=10)
    assert len(index.overlaps("chr1", 5, 15)) == 1
    assert index.overlaps("chr2", 5, 15) == []


def test_count_alignments_filters_mapq_and_primary(tmp_path):
    bam = _write_bam(tmp_path, [("chr1", 1000)], [
        (0, 60, 0, 0, [("M", 20)], "A" * 20),
        (0, 5, 0, 0, [("M", 20)], "A" * 20),
        (0x100, 60, 0, 0, [("M", 20)], "A" * 20),
        (0, 60, 0, 500, [("M", 20)], "A" * 20),
    ])
    counts, considered = count_alignments(bam, [("chr1", "g1", 0, 100, "+")], min_mapq=30)
    assert counts["g1"] == 1
    assert considered == 1


def test_bam_gene_counts_operator(tmp_path):
    bam = _write_bam(tmp_path, [("chr1", 1000)], [
        (0, 60, 0, 10, [("M", 10)], "A" * 10),
        (0, 60, 0, 15, [("M", 10)], "A" * 10),
    ])
    annotation = _gff_form([("chr1", 1, 100, "g1"), ("chr1", 200, 300, "g2")])
    summary = _run(BamGeneCountsStep(), {"output": "out"}, [
        FileArtifact("bam", {"reads": bam}), annotation], tmp_path)
    assert summary["n_features"] == 2
    assert summary["total_counts"] == 2.0


def test_counts_normalize_values(tmp_path):
    form = Form(
        np.array([[100.0, 1000.0], [200.0, 2000.0]]),
        ["feature", "statistic"],
        {"feature": {"g1": 0, "g2": 1},
         "statistic": {"counts": 0, "length": 1}})
    summary = _run(CountsNormalizeStep(), {"output": "out"}, [form], tmp_path)
    assert summary["total_counts"] == 300.0


def test_counts_normalize_rejects_bad_lengths(tmp_path):
    form = Form(np.array([[10.0, 0.0]]), ["feature", "statistic"],
                {"feature": {"g1": 0}, "statistic": {"counts": 0, "length": 1}})
    with pytest.raises(StepError):
        _run(CountsNormalizeStep(), {"output": "out"}, [form], tmp_path)


def test_bam_gene_bias_ratio(tmp_path):
    bam = _write_bam(tmp_path, [("chr1", 1000)], [
        (0, 60, 0, 0, [("M", 10)], "A" * 10),
        (0, 60, 0, 90, [("M", 10)], "A" * 10),
    ])
    annotation = _gff_form([("chr1", 1, 100, "g1")])
    summary = _run(BamGeneBiasStep(), {"output": "out", "bins": 5}, [
        FileArtifact("bam", {"reads": bam}), annotation], tmp_path)
    assert summary["n_features"] == 1
