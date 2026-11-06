"""B2 sequencing QC operators: hand-built FASTQ/BAM inputs with exact values."""
from __future__ import annotations

import gzip
import struct

import numpy as np
import pytest

from src.core import FileArtifact, StepError
from src.task.context import Context
from src.task.step.steps._fastq_utils import iter_fastq, open_text
from src.task.step.steps.bam_flagstat import BamFlagstatStep, flagstat_counts, iter_bam_records
from src.task.step.steps.fastq_adapter_scan import FastqAdapterScanStep
from src.task.step.steps.fastq_quality_profile import FastqQualityProfileStep
from src.task.step.steps.fastq_stats import FastqStatsStep


def _fastq(tmp_path, reads, name="reads.fastq", compress=False):
    lines = []
    for index, (sequence, quality) in enumerate(reads):
        lines.extend((f"@read{index}", sequence, "+", quality))
    body = ("\n".join(lines) + "\n").encode("ascii")
    path = tmp_path / name
    if compress:
        with gzip.open(path, "wb") as handle:
            handle.write(body)
    else:
        path.write_bytes(body)
    return FileArtifact("fastq", {"r1": str(path)}, {})


def _run(step, params, inputs, tmp_path):
    if getattr(step, "name", None) in (None, "", "unnamed"):
        step.name = step.definition["id"]
    ctx = Context(tmp_path / "task", {})
    ctx.step_params = dict(params)
    step.run(ctx, inputs)
    return ctx, step.export(ctx)


def _stat_map(form):
    axis = form.dims[0]
    return {
        label: float(form.data[index, 0])
        for label, index in form.labels[axis].items()
    }


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
    for flag, mapq, ref_id, next_ref_id in records:
        record = struct.pack(
            "<iiBBHHHiiii", ref_id, 0, 2, mapq, 0, 0, flag, 0, next_ref_id, 0, 0
        ) + b"r\x00"
        body += struct.pack("<i", len(record)) + record
    path = tmp_path / name
    with gzip.open(path, "wb") as handle:
        handle.write(header + body)
    return FileArtifact("bam", {"alignments": str(path)}, {})


def test_fastq_stats_hand_counts(tmp_path):
    artifact = _fastq(
        tmp_path,
        (("ACGT", "IIII"), ("GGNN", "!!!!"), ("AT", "II")),
    )
    ctx, report = _run(FastqStatsStep(), {}, [artifact], tmp_path)
    stats = _stat_map(ctx["fastq_stats"])
    assert stats["n_reads"] == 3
    assert stats["n_bases"] == 10
    assert stats["min_length"] == 2
    assert stats["max_length"] == 4
    assert stats["mean_length"] == pytest.approx(10 / 3)
    assert stats["gc_fraction"] == pytest.approx(0.4)
    assert stats["mean_quality"] == pytest.approx(24.0)
    assert stats["q20_fraction"] == pytest.approx(0.6)
    assert stats["q30_fraction"] == pytest.approx(0.6)
    assert stats["n_reads_with_n"] == 1
    assert report["n_reads"] == 3


def test_fastq_stats_reads_gzip_and_max_reads(tmp_path):
    artifact = _fastq(
        tmp_path,
        (("ACGT", "IIII"), ("GGNN", "!!!!")),
        name="reads.fastq.gz",
        compress=True,
    )
    ctx, _ = _run(FastqStatsStep(), {"max_reads": 1, "output": "stats"}, [artifact], tmp_path)
    stats = _stat_map(ctx["stats"])
    assert stats["n_reads"] == 1
    assert stats["n_bases"] == 4


def test_fastq_utils_rejects_truncated_record(tmp_path):
    path = tmp_path / "bad.fastq"
    path.write_text("@r1\nACGT\n+\n", encoding="ascii")
    with open_text(str(path)) as stream:
        with pytest.raises(ValueError):
            list(iter_fastq(stream))


def test_fastq_quality_profile_per_cycle(tmp_path):
    artifact = _fastq(
        tmp_path,
        (("ACGT", "IIII"), ("GGNN", "!!!!"), ("AT", "II")),
    )
    ctx, report = _run(FastqQualityProfileStep(), {}, [artifact], tmp_path)
    form = ctx["fastq_quality_profile"]
    assert form.dims == ["position", "mean_quality"]
    means = {label: float(form.data[index, 0]) for label, index in form.labels["position"].items()}
    assert means == pytest.approx({
        "1": 80 / 3,
        "2": 80 / 3,
        "3": 20.0,
        "4": 20.0,
    })
    assert report["n_positions"] == 4


def test_fastq_adapter_scan_default_panel(tmp_path):
    artifact = _fastq(
        tmp_path,
        (
            ("AGATCGGAAGAGCACACGTCTGAACTCCAGTCAC", "I" * 34),
            ("TTTTAGATCGGAAGAG", "I" * 16),
            ("CTGTCTCTTATACACATCT", "I" * 19),
            ("ACGTACGT", "I" * 8),
        ),
    )
    ctx, report = _run(FastqAdapterScanStep(), {}, [artifact], tmp_path)
    form = ctx["fastq_adapter_scan"]
    assert form.dims == ["adapter", "metric"]
    table = {
        label: [float(value) for value in form.data[index]]
        for label, index in form.labels["adapter"].items()
    }
    assert table["illumina"] == [2.0, 0.5]
    assert table["nextera"] == [1.0, 0.25]
    assert table["small_rna"] == [0.0, 0.0]
    assert report["adapters"]["illumina"] == 2


def test_fastq_adapter_scan_custom_panel_and_mismatch(tmp_path):
    artifact = _fastq(
        tmp_path,
        (("GGGGACGTACGT", "I" * 12), ("ACGTACGTACGT", "I" * 12)),
    )
    ctx, _ = _run(
        FastqAdapterScanStep(),
        {"adapters": "custom:ACGTACGT", "min_overlap": 8, "max_mismatches": 1},
        [artifact],
        tmp_path,
    )
    form = ctx["fastq_adapter_scan"]
    assert form.data.shape == (1, 2)
    assert float(form.data[0, 0]) == 2.0


def test_bam_flagstat_matches_flag_counts(tmp_path):
    records = [
        (0x43, 60, 0, 0),   # paired, proper, read1, mapped
        (0x49, 60, 0, 0),   # paired, read1, mate unmapped -> singleton
        (0x85, 0, 0, 0),    # paired, read2, unmapped
        (0x440, 60, 0, 0),  # duplicate, read1, unpaired
        (0x101, 0, 0, 0),   # secondary
        (0x801, 0, 0, 0),   # supplementary
        (0x43, 10, 0, 1),   # mate on another chromosome
    ]
    artifact = _bam(tmp_path, records)
    ctx, report = _run(BamFlagstatStep(), {}, [artifact], tmp_path)
    stats = _stat_map(ctx["bam_flagstat"])
    assert stats == {
        "total": 7,
        "primary": 5,
        "secondary": 1,
        "supplementary": 1,
        "duplicates": 1,
        "primary_duplicates": 1,
        "mapped": 6,
        "primary_mapped": 4,
        "paired_in_sequencing": 6,
        "read1": 4,
        "read2": 1,
        "properly_paired": 2,
        "with_itself_and_mate_mapped": 4,
        "singletons": 1,
        "mate_mapped_to_different_chr": 1,
        "mate_mapped_to_different_chr_mapq5": 1,
    }
    assert report["total"] == 7


def test_bam_flagstat_rejects_non_bam(tmp_path):
    artifact = _fastq(tmp_path, (("ACGT", "IIII"),))
    with pytest.raises(StepError):
        _run(BamFlagstatStep(), {}, [artifact], tmp_path)


def test_bam_reader_iterates_only_requested_records(tmp_path):
    artifact = _bam(tmp_path, [(0x43, 60, 0, 0), (0x43, 60, 0, 0)])
    records = list(iter_bam_records(artifact.files["alignments"], max_records=1))
    assert len(records) == 1
    counts = flagstat_counts(records)
    assert counts["total"] == 1
