"""Batch 3 alignment operators: hand-built BAM/FASTA inputs with exact values."""
from __future__ import annotations

import gzip
import struct

import pytest

from src.core import FileArtifact, StepError
from src.task.context import Context
from src.task.step.steps._bam_utils import iter_records, read_fasta, read_header
from src.task.step.steps.alignment_coverage import AlignmentCoverageStep
from src.task.step.steps.alignment_insert_size import AlignmentInsertSizeStep
from src.task.step.steps.consensus_sequence import ConsensusSequenceStep
from src.task.step.steps.pileup_variants import PileupVariantsStep

_SEQ_CODES = "=ACMGRSVTWYHKDBN"
_CIGAR_OPS = "MIDNSHP=X"


def _encode_sequence(sequence: str) -> bytes:
    out = bytearray()
    for index in range(0, len(sequence), 2):
        high = _SEQ_CODES.index(sequence[index])
        low = _SEQ_CODES.index(sequence[index + 1]) if index + 1 < len(sequence) else 0
        out.append((high << 4) | low)
    return bytes(out)


def _write_bam(tmp_path, references, records, name="tiny.bam"):
    header = b"BAM\x01" + struct.pack("<i", 0) + struct.pack("<i", len(references))
    for reference, length in references:
        encoded = reference.encode() + b"\x00"
        header += struct.pack("<i", len(encoded)) + encoded + struct.pack("<i", length)
    body = b""
    for record in records:
        flag, mapq, ref_id, pos = record[:4]
        cigar = record[4]
        sequence = record[5]
        tlen = record[6] if len(record) > 6 else 0
        read_name = b"r\x00"
        cigar_bytes = b"".join(
            struct.pack("<I", (length << 4) | _CIGAR_OPS.index(operation))
            for operation, length in cigar
        )
        packed = struct.pack(
            "<iiBBHHHiiii", ref_id, pos, len(read_name), mapq, 0, len(cigar),
            flag, len(sequence), -1, -1, tlen,
        )
        payload = packed + read_name + cigar_bytes + _encode_sequence(sequence) + bytes([40]) * len(sequence)
        body += struct.pack("<i", len(payload)) + payload
    path = tmp_path / name
    with gzip.open(path, "wb") as handle:
        handle.write(header + body)
    return str(path)


def _write_fasta(tmp_path, sequences, name="ref.fasta"):
    lines = []
    for header, sequence in sequences.items():
        lines.append(f">{header}")
        for index in range(0, len(sequence), 60):
            lines.append(sequence[index:index + 60])
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return str(path)


def _run(step, params, inputs, tmp_path):
    if getattr(step, "name", None) in (None, "", "unnamed"):
        step.name = step.definition["id"]
    ctx = Context(tmp_path / "task", {})
    ctx.step_params = dict(params)
    step.run(ctx, inputs)
    return ctx, step.export(ctx)


def _stat_map(form):
    axis = form.dims[0]
    return {label: float(form.data[index, 0]) for label, index in form.labels[axis].items()}


def test_alignment_coverage_hand_depth(tmp_path):
    path = _write_bam(tmp_path, [("chr1", 12)], [
        (0, 60, 0, 0, [("M", 5)], "ACGTA"),
        (0, 60, 0, 3, [("M", 5)], "TACGT"),
        (0x4, 60, 0, 0, [("M", 5)], "ACGTA"),
        (0x100, 60, 0, 0, [("M", 5)], "ACGTA"),
    ])
    ctx, report = _run(AlignmentCoverageStep(), {}, [FileArtifact("bam", {"alignments": path}, {})], tmp_path)
    stats = _stat_map(ctx["alignment_coverage"])
    assert stats["n_reads"] == 4
    assert stats["n_mapped"] == 2
    assert stats["genome_length"] == 12
    assert stats["covered_bases"] == 8
    assert stats["max_depth"] == 2
    assert stats["mean_depth"] == pytest.approx(10 / 12)
    assert stats["breadth_1x"] == pytest.approx(8 / 12)
    assert stats["breadth_5x"] == 0.0
    assert report["n_mapped"] == 2


def test_alignment_insert_size_hand_stats(tmp_path):
    records = [
        (65, 60, 0, 0, [("M", 10)], "A" * 10, 100),
        (65, 60, 0, 20, [("M", 10)], "A" * 10, 200),
        (65, 60, 0, 40, [("M", 10)], "A" * 10, 300),
        (129, 60, 0, 0, [("M", 10)], "A" * 10, -100),
        (1, 60, 0, 0, [("M", 10)], "A" * 10, 150),
        (0, 60, 0, 0, [("M", 10)], "A" * 10, 0),
    ]
    path = _write_bam(tmp_path, [("chr1", 1000)], records)
    ctx, report = _run(AlignmentInsertSizeStep(), {}, [FileArtifact("bam", {"alignments": path}, {})], tmp_path)
    stats = _stat_map(ctx["alignment_insert_size"])
    assert stats["n_pairs"] == 3
    assert stats["mean_insert_size"] == pytest.approx(200.0)
    assert stats["median_insert_size"] == pytest.approx(200.0)
    assert stats["std_insert_size"] == pytest.approx(81.64965809)
    assert stats["min_insert_size"] == 100.0
    assert stats["max_insert_size"] == 300.0
    assert stats["p25_insert_size"] == pytest.approx(150.0)
    assert stats["p75_insert_size"] == pytest.approx(250.0)
    assert report["n_pairs"] == 3


def test_pileup_variants_calls_majority_allele(tmp_path):
    bam = _write_bam(tmp_path, [("chr1", 8)], [
        (0, 60, 0, 0, [("M", 1)], "G"),
        (0, 60, 0, 0, [("M", 1)], "G"),
        (0, 60, 0, 0, [("M", 1)], "G"),
        (0, 60, 0, 0, [("M", 1)], "G"),
        (0, 60, 0, 0, [("M", 1)], "G"),
        (0, 60, 0, 0, [("M", 1)], "G"),
    ])
    fasta = _write_fasta(tmp_path, {"chr1": "ACGTACGT"})
    ctx, report = _run(
        PileupVariantsStep(),
        {"min_depth": 5, "min_alt_fraction": 0.8, "min_alt_count": 2},
        [FileArtifact("bam", {"alignments": bam}, {}), FileArtifact("fasta", {"genome": fasta}, {})],
        tmp_path,
    )
    assert report["n_variants"] == 1
    assert report["n_snps"] == 1
    lines = [line for line in __import__("pathlib").Path(ctx["pileup_variants"].files["variants"]).read_text().splitlines() if not line.startswith("#")]
    assert lines == ["chr1\t1\t.\tA\tG\t.\tPASS\tDP=6;AF=1.0000"]


def test_consensus_sequence_masks_low_depth(tmp_path):
    bam = _write_bam(tmp_path, [("chr1", 4)], [
        (0, 60, 0, 0, [("M", 1)], "G"),
        (0, 60, 0, 0, [("M", 1)], "G"),
        (0, 60, 0, 0, [("M", 1)], "G"),
        (0, 60, 0, 0, [("M", 1)], "G"),
        (0, 60, 0, 0, [("M", 1)], "G"),
        (0, 60, 0, 0, [("M", 1)], "G"),
    ])
    fasta = _write_fasta(tmp_path, {"chr1": "ACGT"})
    ctx, report = _run(
        ConsensusSequenceStep(),
        {"min_depth": 5, "min_fraction": 0.6},
        [FileArtifact("bam", {"alignments": bam}, {}), FileArtifact("fasta", {"genome": fasta}, {})],
        tmp_path,
    )
    assert report["n_called_bases"] == 1
    assert report["n_N_bases"] == 3
    assert report["n_substitutions"] == 1
    body = __import__("pathlib").Path(ctx["consensus_sequence"].files["genome"]).read_text().splitlines()
    assert body[0].startswith(">chr1")
    assert body[1] == "GNNN"


def test_helpers_reject_non_bam(tmp_path):
    path = tmp_path / "not.bam"
    path.write_bytes(b"hello")
    with pytest.raises(ValueError):
        read_header(str(path))
    with pytest.raises(StepError):
        _run(AlignmentCoverageStep(), {}, [FileArtifact("bam", {"alignments": str(path)}, {})], tmp_path)


def test_read_fasta_and_records_roundtrip(tmp_path):
    fasta = _write_fasta(tmp_path, {"chr1": "ACGT", "chr2": "TTTT"})
    assert read_fasta(fasta) == {"chr1": "ACGT", "chr2": "TTTT"}
    bam = _write_bam(tmp_path, [("chr1", 4)], [(0, 60, 0, 1, [("M", 2)], "AC")])
    _text, references = read_header(bam)
    assert references == [("chr1", 4)]
    records = list(iter_records(bam, decode_sequence=True))
    assert len(records) == 1
    assert records[0]["seq"] == "AC"
    assert records[0]["pos"] == 1
