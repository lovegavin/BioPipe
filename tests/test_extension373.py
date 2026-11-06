"""Contract tests for the FASTQ preprocessing operators."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.core import FileArtifact, StepError
from src.task.step.steps.fastq_adapter_trim import FastqAdapterTrimStep
from src.task.step.steps.fastq_deduplicate import FastqDeduplicateStep
from src.task.step.steps.fastq_quality_trim import FastqQualityTrimStep
from src.task.step.steps._fastq_transform import adapter_trim_index, quality_trim_index


class Ctx(dict):
    def __init__(self, params, root):
        super().__init__()
        self.step_params = dict(params)
        self._root = Path(root)

    def artifact_path(self, name):
        path = self._root / name
        path.mkdir(parents=True, exist_ok=True)
        return path


def _artifact(tmp_path, records, name="reads.fastq"):
    text = "".join(f"@r{i}\n{seq}\n+\n{qual}\n" for i, (seq, qual) in enumerate(records))
    path = tmp_path / name
    path.write_bytes(text.encode("utf-8"))
    artifact = FileArtifact("fastq", {"reads": str(path)}, info={"representation": "fastq"})
    artifact.fingerprints = {"reads": FileArtifact._stamp(path)}
    return artifact


def _run(step, tmp_path, artifact, params):
    ctx = Ctx({"output": "out", **params}, tmp_path / "artifacts")
    step.run(ctx, [artifact])
    return ctx, list(step.export(ctx).items())


def test_quality_trim_index_matches_bwa_rule():
    assert quality_trim_index("IIIII+++++", 20) == 5
    assert quality_trim_index("IIIIIIIIII", 20) == 10
    assert quality_trim_index("IIIII!!!!!", 30) == 5


def test_quality_trim_writes_sequence_and_stats(tmp_path):
    artifact = _artifact(tmp_path, [("ACGTACGTAC", "IIIII+++++"), ("TTTT", "IIII")])
    ctx, export = _run(FastqQualityTrimStep(), tmp_path, artifact, {"min_quality": 20})
    stats = dict(export)
    assert stats["reads_in"] == 2
    assert stats["reads_out"] == 2
    assert stats["bases_in"] == 14
    assert stats["bases_out"] == 9
    assert stats["bases_trimmed"] == 5
    text = Path(stats["file"]).read_text(encoding="utf-8")
    assert "ACGTACGTAC" not in text and "@r0\nACGTA\n" in text


def test_quality_trim_drops_short_reads(tmp_path):
    artifact = _artifact(tmp_path, [("ACGT", "IIII"), ("ACGTACGT", "IIIII+++")])
    _, export = _run(FastqQualityTrimStep(), tmp_path, artifact, {"min_quality": 20, "min_length": 5})
    stats = dict(export)
    assert stats["reads_in"] == 2 and stats["reads_out"] == 1 and stats["reads_dropped"] == 1
    assert len(stats["result_files"]) == 1 and stats["result_files"][0]["format"] == "fastq"


def test_quality_trim_rejects_bad_quality(tmp_path):
    artifact = _artifact(tmp_path, [("ACGT", "IIII")])
    with pytest.raises(StepError, match="min_quality"):
        _run(FastqQualityTrimStep(), tmp_path, artifact, {"min_quality": 50})


def test_adapter_trim_exact_and_partial():
    adapter = "AGATCGGAAGAGC"
    assert adapter_trim_index("ACGTAGATCGGAAGAGC", adapter) == 4
    assert adapter_trim_index("ACGTACGTACGTAGATCG", adapter) == 12
    assert adapter_trim_index("ACGTACGT", adapter) == 8


def test_adapter_trim_operator_counts(tmp_path):
    artifact = _artifact(
        tmp_path,
        [("ACGTAGATCGGAAGAGC", "I" * 17), ("ACGTACGT", "IIIIIIII")],
    )
    _, export = _run(
        FastqAdapterTrimStep(), tmp_path, artifact, {"adapter": "AGATCGGAAGAGC"}
    )
    stats = dict(export)
    assert stats["reads_in"] == 2 and stats["reads_with_adapter"] == 1
    assert stats["bases_in"] == 25 and stats["bases_out"] == 12
    assert "@r0\nACGT\n" in Path(stats["file"]).read_text(encoding="utf-8")


def test_deduplicate_keeps_first_occurrence(tmp_path):
    artifact = _artifact(
        tmp_path, [("AAAA", "IIII"), ("AAAA", "IIII"), ("CCCC", "IIII")]
    )
    _, export = _run(FastqDeduplicateStep(), tmp_path, artifact, {})
    stats = dict(export)
    assert stats["reads_in"] == 3 and stats["reads_unique"] == 2
    assert stats["reads_duplicate"] == 1
    assert stats["duplicate_fraction"] == pytest.approx(1 / 3)
    text = Path(stats["file"]).read_text(encoding="utf-8")
    assert text.count("@r0") == 1 and text.count("@r2") == 1


def test_deduplicate_can_collapse_reverse_complements(tmp_path):
    artifact = _artifact(tmp_path, [("AAAACCCC", "IIIIIIII"), ("GGGGTTTT", "IIIIIIII")])
    _, export = _run(FastqDeduplicateStep(), tmp_path, artifact, {"collapse_reverse_complements": True})
    stats = dict(export)
    assert stats["reads_in"] == 2 and stats["reads_unique"] == 1


def test_max_records_limits_input(tmp_path):
    artifact = _artifact(tmp_path, [("AAAA", "IIII"), ("CCCC", "IIII")])
    _, export = _run(FastqDeduplicateStep(), tmp_path, artifact, {"max_records": 1})
    stats = dict(export)
    assert stats["reads_in"] == 1 and stats["reads_unique"] == 1


def test_malformed_fastq_raises(tmp_path):
    path = tmp_path / "bad.fastq"
    path.write_bytes(b"@r0\nACGT\n+\nII\n")
    artifact = FileArtifact("fastq", {"reads": str(path)}, info={"representation": "fastq"})
    artifact.fingerprints = {"reads": FileArtifact._stamp(path)}
    with pytest.raises(StepError, match="malformed"):
        _run(FastqDeduplicateStep(), tmp_path, artifact, {})
