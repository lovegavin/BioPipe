import gzip
from pathlib import Path

import numpy as np
import pytest

from src.core import FileArtifact, Form, StepError
from src.task.context import Context
from src.task.step.steps.fastq_duplication_profile import FastqDuplicationProfileStep
from src.task.step.steps.fastq_gc_distribution import FastqGcDistributionStep
from src.task.step.steps.fastq_overrepresented import FastqOverrepresentedStep

TAB = chr(9)
READS = ["GCTAGCTAGCTAGCTAGCTA", "GCTAGCTAGCTAGCTAGCTA", "GCTAGCTAGCTAGCTAGCTA",
         "AAAATTTTAAAATTTTAAAA", "AAAATTTTAAAATTTTAAAA",
         "GGGGCCCCGGGGCCCCGGGG", "ATATATATATATATATATAT", "GCGCGCGCGCGCGCGCGCGC"]


def write_fastq(path, sequences):
    lines = []
    for index, sequence in enumerate(sequences):
        lines.append(f"@r{index}")
        lines.append(sequence)
        lines.append("+")
        lines.append("I" * len(sequence))
    text = "\n".join(lines) + "\n"
    if str(path).endswith(".gz"):
        with gzip.open(path, "wt") as handle:
            handle.write(text)
    else:
        Path(path).write_text(text)


def artifact(path):
    path = Path(path)
    return FileArtifact("fastq", {"reads": path}, info={"representation": "fastq"})


class Ctx(Context):
    def __init__(self, params):
        self.step_params = params
        self._values = {}

    def __setitem__(self, key, value):
        self._values[key] = value

    def __getitem__(self, key):
        return self._values[key]


def run(step, path, params):
    ctx = Ctx(params)
    step.run(ctx, [artifact(path)])
    return ctx[params.get("output", "result")]


def test_duplication_levels(tmp_path):
    path = tmp_path / "reads.fastq"
    write_fastq(path, READS)
    form = run(FastqDuplicationProfileStep(), path, {"output": "result"})
    rows = {label: form.data[i].tolist() for label, i in form.labels["level"].items()}
    assert rows["1"][0] == 3 and rows["2"][0] == 1 and rows["3"][0] == 1
    assert rows["1"][1] == pytest.approx(3 / 8)
    assert form.data.shape == (15, 3)
    assert form.info["deduplicated_percentage"] == pytest.approx(5 / 8 * 100)


def test_duplication_max_reads(tmp_path):
    path = tmp_path / "reads.fastq.gz"
    write_fastq(path, READS)
    form = run(FastqDuplicationProfileStep(), path, {"output": "reads", "max_reads": 2})
    assert form.info["total_reads"] == 2
    assert form.info["unique_sequences"] == 1


def test_overrepresented_threshold(tmp_path):
    path = tmp_path / "reads.fastq"
    write_fastq(path, READS)
    form = run(FastqOverrepresentedStep(), path, {"output": "result", "threshold": 0.3})
    assert form.data.shape[0] == 1
    assert form.labels["sequence"]["GCTAGCTAGCTAGCTAGCTA"] == 0
    assert form.data[0][0] == 3.0
    assert form.info["n_overrepresented"] == 1


def test_overrepresented_none(tmp_path):
    path = tmp_path / "reads.fastq"
    write_fastq(path, ["ACGT" * 5] * 8)
    form = run(FastqOverrepresentedStep(), path, {"output": "result", "threshold": 0.5})
    assert form.data.shape == (1, 2) and form.info["n_overrepresented"] == 1


def test_gc_distribution(tmp_path):
    path = tmp_path / "reads.fastq"
    write_fastq(path, ["GGGGCCCCAA", "AAAAAAAAAA", "GGGGCCCCAA", "ACGTACGTAC"])
    form = run(FastqGcDistributionStep(), path, {"output": "gc"})
    assert form.data.shape == (101, 2)
    counts = form.data[:, 0]
    assert counts[80] == 2 and counts[0] == 1 and counts[50] == 1
    assert form.info["mean_gc"] == pytest.approx((80 + 0 + 80 + 50) / 4)
    assert form.info["mode_gc"] == 80


def test_gc_empty_raises(tmp_path):
    path = tmp_path / "empty.fastq"
    path.write_text("")
    with pytest.raises(StepError):
        run(FastqGcDistributionStep(), path, {"output": "gc"})
