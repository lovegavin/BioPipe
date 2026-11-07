"""Tests for BAM alignment QC operators (MAPQ, read length, summary)."""
from __future__ import annotations

import gzip
import struct

import numpy as np
import pytest

from src.core import FileArtifact
from src.task.step.steps.bam_alignment_summary import BamAlignmentSummaryStep
from src.task.step.steps.bam_mapq_distribution import BamMapqDistributionStep
from src.task.step.steps.bam_read_length_stats import BamReadLengthStatsStep

_OPS = "MIDNSHP=X"


class Ctx(dict):
    def __init__(self, step_params=None):
        super().__init__()
        self.step_params = dict(step_params or {})


def _bam(tmp_path, records, name="tiny.bam"):
    header = (
        b"BAM\x01"
        + struct.pack("<i", 0)
        + struct.pack("<i", 1)
        + struct.pack("<i", 5)
        + b"chr1\x00"
        + struct.pack("<i", 1000)
    )
    body = b""
    for index, record in enumerate(records):
        flag = record["flag"]
        mapq = record["mapq"]
        cigar = record["cigar"]
        length = sum(size for op, size in cigar if op in "MIS=X")
        packed = b"".join(
            struct.pack("<I", (size << 4) | _OPS.index(op)) for op, size in cigar
        )
        payload = struct.pack(
            "<iiBBHHHiiii",
            0,
            record.get("pos", 0),
            2,
            mapq,
            0,
            len(cigar),
            flag,
            length,
            0,
            0,
            0,
        ) + b"r\x00"
        payload += packed
        payload += bytes((length + 1) // 2)
        payload += b"\xff" * length
        body += struct.pack("<i", len(payload)) + payload
    path = tmp_path / name
    with gzip.open(path, "wb") as handle:
        handle.write(header + body)
    return FileArtifact("bam", {"alignments": str(path)}, {})


def _run(step, artifact, params):
    ctx = Ctx(params)
    step.run(ctx, [artifact])
    return ctx[params.get("output", "out")]


def test_mapq_histogram_hand_counts(tmp_path):
    artifact = _bam(
        tmp_path,
        [
            {"flag": 0x1 | 0x2, "mapq": 60, "cigar": [("M", 10)]},
            {"flag": 0x1 | 0x2 | 0x10, "mapq": 30, "cigar": [("M", 5), ("S", 2)]},
            {"flag": 0x400 | 0x1, "mapq": 0, "cigar": [("M", 10)]},
            {"flag": 0x4, "mapq": 0, "cigar": []},
        ],
    )
    form = _run(BamMapqDistributionStep(), artifact, {"output": "out", "max_mapq": 60})
    counts = form.data[:, 0]
    assert form.info["n_reads"] == 3
    assert counts[60] == 1 and counts[30] == 1 and counts[0] == 1
    assert counts.sum() == 3
    assert form.info["mean_mapq"] == pytest.approx(30.0)
    assert form.info["median_mapq"] == 30.0
    assert form.info["pct_ge_20"] == pytest.approx(2 / 3)
    assert form.labels["mapq"]["60"] == 60


def test_read_length_histogram_hand_counts(tmp_path):
    artifact = _bam(
        tmp_path,
        [
            {"flag": 0x1 | 0x2, "mapq": 60, "cigar": [("M", 10)]},
            {"flag": 0x1 | 0x2, "mapq": 30, "cigar": [("M", 5), ("S", 2)]},
            {"flag": 0x1 | 0x2, "mapq": 20, "cigar": [("M", 10)]},
        ],
    )
    form = _run(BamReadLengthStatsStep(), artifact, {"output": "out", "max_length": 1000})
    assert form.info["n_reads"] == 3
    assert form.info["min_length"] == 7
    assert form.info["max_length"] == 10
    assert form.info["mean_length"] == pytest.approx(9.0)
    assert form.info["median_length"] == 10.0
    rows = {key: form.data[index, 0] for key, index in form.labels["read_length"].items()}
    assert rows["10"] == 2 and rows["7"] == 1


def test_read_length_overflow_bin(tmp_path):
    artifact = _bam(
        tmp_path,
        [{"flag": 0, "mapq": 60, "cigar": [("M", 50)]}],
    )
    form = _run(BamReadLengthStatsStep(), artifact, {"output": "out", "max_length": 20})
    assert form.info["overflow_reads"] == 1
    assert form.labels["read_length"]["20+"] == len(form.labels["read_length"]) - 1


def test_alignment_summary_counts(tmp_path):
    artifact = _bam(
        tmp_path,
        [
            {"flag": 0x1 | 0x2, "mapq": 60, "cigar": [("M", 10)]},
            {"flag": 0x1 | 0x2 | 0x10, "mapq": 30, "cigar": [("M", 5), ("S", 2)]},
            {"flag": 0x400 | 0x1, "mapq": 0, "cigar": [("M", 10)]},
            {"flag": 0x4, "mapq": 0, "cigar": []},
        ],
    )
    form = _run(BamAlignmentSummaryStep(), artifact, {"output": "out"})
    values = {key: form.data[index, 0] for key, index in form.labels["statistic"].items()}
    assert values["total_reads"] == 4
    assert values["mapped_reads"] == 3
    assert values["unmapped_reads"] == 1
    assert values["primary_reads"] == 3
    assert values["duplicate_reads"] == 1
    assert values["paired_reads"] == 3
    assert values["proper_pair_fraction"] == pytest.approx(2 / 3)
    assert values["duplicate_fraction"] == pytest.approx(1 / 3)
    assert values["reverse_fraction"] == pytest.approx(1 / 3)
    assert values["clipped_fraction"] == pytest.approx(1 / 3)
    assert values["mean_mapq"] == pytest.approx(30.0)


def test_summary_rejects_unknown_artifact(tmp_path):
    bad = tmp_path / "x.bam"
    bad.write_bytes(b"not a bam")
    artifact = FileArtifact("txt", {"alignments": str(bad)}, {})
    with pytest.raises(Exception):
        _run(BamAlignmentSummaryStep(), artifact, {"output": "out"})
