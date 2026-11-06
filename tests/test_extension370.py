"""Contract tests for the ATAC-seq QC operators."""
from __future__ import annotations

import gzip
import struct

import numpy as np
import pytest

from src.core import FileArtifact, Form, StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.atac_fragment_size import AtacFragmentSizeStep
from src.task.step.steps.atac_peak_quality import AtacPeakQualityStep
from src.task.step.steps.atac_tss_enrichment import AtacTssEnrichmentStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)


def _bam(tmp_path, fragments, name="tiny.bam"):
    header = (
        b"BAM\x01"
        + struct.pack("<i", 0)
        + struct.pack("<i", 1)
        + struct.pack("<i", 5)
        + b"chr1\x00"
        + struct.pack("<i", 20000)
    )
    body = b""
    for pos, tlen, flag in fragments:
        record = struct.pack(
            "<iiBBHHHiiii", 0, pos, 2, 60, 0, 0, flag, 0, 0, pos + tlen, tlen
        ) + b"r\x00"
        body += struct.pack("<i", len(record)) + record
    path = tmp_path / name
    with gzip.open(path, "wb") as handle:
        handle.write(header + body)
    return FileArtifact("bam", {"alignments": str(path)}, {})


def _bed(rows, name="peaks.bed"):
    encoder = LabelEncoder()
    chrom_codes = encoder.fit_transform([row[0] for row in rows])
    data = np.zeros((len(rows), 4), dtype=np.float64)
    for index, (chrom, start, end, strand) in enumerate(rows):
        data[index, 0] = chrom_codes[index]
        data[index, 1] = start
        data[index, 2] = end
        data[index, 3] = 0 if strand == "+" else 1
    labels = {"region": {}, "field": {"chrom": 0, "chromStart": 1,
                                     "chromEnd": 2, "strand": 3}}
    labels["region"] = {f"peak{index}": index for index in range(len(rows))}
    strand_encoder = LabelEncoder()
    strand_encoder.fit_transform(["+", "-"])
    return Form(data, ["region", "field"], labels,
                info={"encoders": {"field": {"chrom": encoder,
                                             "strand": strand_encoder}}})


def _run(step, params, inputs):
    merged = dict(params)
    merged["output"] = "out"
    ctx = Ctx(merged)
    step.run(ctx, inputs)
    return ctx["out"], step.export(ctx)


def test_fragment_histogram_and_fractions(tmp_path):
    artifact = _bam(tmp_path, [(100, 50, 0x43), (1000, 200, 0x43), (2000, 350, 0x43)])
    form, report = _run(AtacFragmentSizeStep(),
                        {"max_length": 400, "output": "fragment_size"}, [artifact])
    assert form.data.shape == (401, 2)
    assert form.data[50, 0] == 1
    assert form.data[200, 0] == 1
    assert form.data[350, 0] == 1
    assert form.data[350, 1] == pytest.approx(1 / 3)
    assert report["nfr_fraction"] == pytest.approx(1 / 3)
    assert report["mononucleosome_fraction"] == pytest.approx(1 / 3)
    assert report["dinucleosome_fraction"] == pytest.approx(1 / 3)
    assert report["nucleosome_fraction"] == pytest.approx(2 / 3)
    assert report["n_fragments"] == 3
    assert report["median_length"] == 200


def test_fragment_histogram_skips_duplicates_and_honours_max_records(tmp_path):
    artifact = _bam(tmp_path, [(100, 50, 0x43), (200, 60, 0x443), (300, 70, 0x43)])
    form, report = _run(AtacFragmentSizeStep(), {"max_length": 200}, [artifact])
    assert report["n_fragments"] == 2
    assert form.data[60, 0] == 0
    form, report = _run(AtacFragmentSizeStep(),
                        {"max_length": 200, "max_records": 1}, [artifact])
    assert report["n_fragments"] == 1


def test_tss_matrix_offsets_and_score(tmp_path):
    artifact = _bam(tmp_path, [
        (4950, 100, 0x43),   # midpoint 5000, offset 0
        (4940, 100, 0x43),   # midpoint 4990, offset -10
        (4990, 100, 0x43),   # midpoint 5040, offset 40
        (4900, 100, 0x43),   # midpoint 4950, offset -50
        (5000, 100, 0x43),   # midpoint 5050, offset 50
    ])
    bed = _bed([("chr1", 5000, 5001, "+")])
    form, report = _run(AtacTssEnrichmentStep(),
                        {"flank": 100, "bin_size": 10, "output": "tss"}, [artifact, bed])
    assert form.data.shape == (1, 20)
    row = form.data[0]
    assert int(row.sum()) == 5
    assert report["n_fragments"] == 5
    assert report["center_mean"] == pytest.approx(0.4)
    assert report["flank_mean"] == pytest.approx(0.1)
    assert report["tss_score"] == pytest.approx(4.0)


def test_tss_negative_strand_uses_end(tmp_path):
    artifact = _bam(tmp_path, [(9940, 100, 0x43)])  # midpoint 9990
    bed = _bed([("chr1", 9989, 9990, "-")])
    form, _report = _run(AtacTssEnrichmentStep(),
                         {"flank": 20, "bin_size": 10, "output": "tss"}, [artifact, bed])
    assert int(form.data.sum()) == 1
    assert form.data[0, 2] == 1


def test_peak_quality_frip(tmp_path):
    artifact = _bam(tmp_path, [(4950, 100, 0x43), (5950, 100, 0x43), (6950, 100, 0x43)])
    bed = _bed([("chr1", 4950, 5050, "+")])
    form, report = _run(AtacPeakQualityStep(), {"output": "peak_quality"}, [artifact, bed])
    values = {label: form.data[index, 0]
              for label, index in form.labels["statistic"].items()}
    assert values["n_fragments"] == 3
    assert values["n_peaks"] == 1
    assert values["fragments_in_peaks"] == 1
    assert values["frip"] == pytest.approx(1 / 3)
    assert values["mean_peak_width"] == 100


def test_empty_bam_reports_step_error(tmp_path):
    artifact = _bam(tmp_path, [(100, 50, 0x4)])
    with pytest.raises(StepError, match="no fragments"):
        _run(AtacFragmentSizeStep(), {"max_length": 200}, [artifact])
