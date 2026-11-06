"""Assembly QC operator tests (extension 378)."""

from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps._assembly_utils import composition, contiguity, gap_runs
from src.task.step.steps.assembly_contig_stats import AssemblyContigStatsStep
from src.task.step.steps.assembly_contiguity import AssemblyContiguityStep
from src.task.step.steps.assembly_gap_stats import AssemblyGapStatsStep


_CODES = {"A": 0, "C": 1, "G": 2, "T": 3, "N": 4}


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)


def _fasta(sequences, names=None):
    names = list(names or [f"seq{index}" for index in range(len(sequences))])
    width = max(len(sequence) for sequence in sequences)
    data = np.full((len(sequences), width), 4, dtype=np.int64)
    for row, sequence in enumerate(sequences):
        for column, base in enumerate(sequence.upper()):
            data[row, column] = _CODES.get(base, 4)
    return Form(
        data,
        dims=["sequence", "position"],
        labels={"sequence": {name: index for index, name in enumerate(names)}, "position": {}},
        info={"sequences": [str(sequence) for sequence in sequences], "alphabet_map": "ACGTN"},
    )


def test_composition_hand_values():
    assert composition("ACGTN") == (2, 1, 5)
    assert composition("") == (0, 0, 0)


def test_gap_runs_hand_values():
    assert gap_runs("ACNNNGTN") == [(2, 5), (7, 8)]
    assert gap_runs("ACGT") == []


def test_contiguity_hand_values():
    summary = contiguity([10, 5, 3])
    assert summary["n_contigs"] == 3
    assert summary["total_bp"] == 18
    assert summary["n50"] == 10
    assert summary["l50"] == 1
    assert summary["n90"] == 3
    assert summary["l90"] == 3
    assert summary["aun"] == pytest.approx((100 + 25 + 9) / 18)
    assert summary["median_length"] == 5


def test_contig_stats_operator_table():
    form = _fasta(["ACGTACGT", "GGNN"], ["chr1", "chr2"])
    step = AssemblyContigStatsStep()
    ctx = Ctx({"output": "out"})
    step.run(ctx, [form])
    out = ctx["out"]
    assert list(out.dims) == ["contig", "statistic"]
    assert out.labels["contig"] == {"chr1": 0, "chr2": 1}
    assert list(out.labels["statistic"]) == ["length", "gc_fraction", "n_fraction", "n_runs"]
    assert out.data[0].tolist() == [8.0, 0.5, 0.0, 0.0]
    assert out.data[1].tolist() == [4.0, 0.5, 0.5, 1.0]
    assert out.info["summary"]["n50"] == 8
    assert out.info["summary"]["gc_fraction"] == pytest.approx(0.5)
    assert step.export(ctx)["n_contigs"] == 2


def test_contiguity_operator_from_table():
    data = np.asarray([[8.0, 0.5], [4.0, 0.5]], dtype=float)
    form = Form(
        data,
        dims=["contig", "statistic"],
        labels={"contig": {"chr1": 0, "chr2": 1}, "statistic": {"length": 0, "gc_fraction": 1}},
    )
    step = AssemblyContiguityStep()
    ctx = Ctx({"output": "out"})
    step.run(ctx, [form])
    out = ctx["out"]
    rows = {name: out.data[index, 0] for name, index in out.labels["statistic"].items()}
    assert rows["n_contigs"] == 2
    assert rows["total_bp"] == 12
    assert rows["n50"] == 8
    assert rows["l50"] == 1
    assert rows["gc_fraction"] == pytest.approx(0.5)
    assert out.info["summary"]["largest_contig"] == "chr1"


def test_contiguity_operator_missing_column():
    form = Form(
        np.asarray([[8.0]], dtype=float),
        dims=["contig", "statistic"],
        labels={"contig": {"chr1": 0}, "statistic": {"gc_fraction": 0}},
    )
    with pytest.raises(StepError, match="missing 'length'"):
        AssemblyContiguityStep().run(Ctx({"output": "out"}), [form])


def test_gap_stats_operator_totals():
    form = _fasta(["ACNNNACGT", "GGGG"], ["chr1", "chr2"])
    step = AssemblyGapStatsStep()
    ctx = Ctx({"output": "out"})
    step.run(ctx, [form])
    out = ctx["out"]
    assert out.labels["contig"] == {"chr1": 0, "chr2": 1}
    assert out.data[0].tolist() == [1.0, 3.0, 3.0]
    assert out.data[1].tolist() == [0.0, 0.0, 0.0]
    exported = step.export(ctx)
    assert exported["n_gaps"] == 1
    assert exported["total_gap_bp"] == 3
    assert exported["gap_fraction"] == pytest.approx(3 / 13)


def test_empty_fasta_is_rejected():
    form = Form(
        np.zeros((0, 0), dtype=np.int64),
        dims=["sequence", "position"],
        labels={"sequence": {}, "position": {}},
        info={"sequences": [], "alphabet_map": "ACGTN"},
    )
    with pytest.raises(StepError, match="empty"):
        AssemblyContigStatsStep().run(Ctx({"output": "out"}), [form])


def test_estimate_memory_contract():
    workspace, output = AssemblyContigStatsStep.estimate_memory([], {}, {})
    assert workspace > 0 and output > 0
