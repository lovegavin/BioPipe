"""Multiple sequence alignment operator tests (extension 380)."""

from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps._msa_utils import (
    alignment_records,
    column_statistics,
    consensus_sequence,
    detect_alphabet,
    identity_matrix,
    trim_alignment,
)
from src.task.step.steps.msa_consensus import MsaConsensusStep
from src.task.step.steps.msa_column_stats import MsaColumnStatsStep
from src.task.step.steps.msa_identity_matrix import MsaIdentityMatrixStep
from src.task.step.steps.msa_trim import MsaTrimStep


_CODES = {"A": 0, "C": 1, "G": 2, "T": 3, "N": 4, "-": 5}


class Ctx(dict):
    def __init__(self, params, root=None):
        super().__init__()
        self.step_params = dict(params)
        self._root = root

    def artifact_path(self, name):
        return str(self._root / name)


def _aligned(sequences, names=None):
    names = list(names or [f"seq{index}" for index in range(len(sequences))])
    width = len(sequences[0])
    data = np.zeros((len(sequences), width), dtype=np.int64)
    for row, sequence in enumerate(sequences):
        for column, base in enumerate(sequence.upper()):
            data[row, column] = _CODES.get(base, 4)
    return Form(
        data,
        dims=["sequence", "position"],
        labels={
            "sequence": {name: index for index, name in enumerate(names)},
            "position": {str(index): index for index in range(width)},
        },
        info={"sequences": list(sequences), "alphabet_map": "ACGTN"},
    )


def test_column_statistics_hand_values():
    names, sequences = ["s1", "s2", "s3"], ["A-GT", "ATGT", "ACGT"]
    stats = column_statistics(sequences, "dna")
    assert list(stats["gap_fraction"]) == pytest.approx([0.0, 1 / 3, 0.0, 0.0])
    assert list(stats["entropy"]) == pytest.approx([0.0, 1.0, 0.0, 0.0])
    assert list(stats["conservation"]) == pytest.approx([1.0, 0.5, 1.0, 1.0])
    assert list(stats["major_fraction"]) == pytest.approx([1.0, 0.5, 1.0, 1.0])
    assert stats["consensus"] == ["A", "C", "G", "T"]


def test_column_stats_operator_matrix():
    form = _aligned(["A-GT", "ATGT", "ACGT"])
    step = MsaColumnStatsStep()
    ctx = Ctx({"output": "stats"})
    step.run(ctx, [form])
    out = ctx["stats"]
    assert list(out.dims) == ["column", "statistic"]
    assert out.data.shape == (4, 4)
    assert out.labels["statistic"] == {
        "gap_fraction": 0,
        "entropy": 1,
        "conservation": 2,
        "major_fraction": 3,
    }
    assert out.data[1, 0] == pytest.approx(1 / 3)
    assert out.data[1, 3] == pytest.approx(0.5)
    assert out.info["n_sequences"] == 3
    assert out.info["alphabet"] == "dna"
    assert out.info["consensus"] == "ACGT"
    assert out.info["conserved_columns"] == 3
    assert out.info["variable_columns"] == 1


def test_consensus_thresholds_and_operator(tmp_path):
    sequences = ["A-GT", "ATGT", "ACGT"]
    stats = column_statistics(sequences, "dna")
    assert consensus_sequence(stats, "dna", 0.5, 0.5) == "ACGT"
    assert consensus_sequence(stats, "dna", 0.5, 0.6) == "ANGT"

    step = MsaConsensusStep()
    ctx = Ctx({"output": "consensus", "min_major_fraction": 0.6})
    step.run(ctx, [_aligned(sequences)])
    out = ctx["consensus"]
    assert out.info["sequences"] == ["ANGT"]
    assert out.info["n_ambiguous"] == 1
    assert out.labels["sequence"] == {"consensus": 0}
    assert step.export(ctx)["consensus"] == "ANGT"


def test_identity_matrix_hand_values(tmp_path):
    sequences = ["A-GT", "ATGT", "ACGT"]
    matrix, comparable = identity_matrix(sequences)
    assert matrix[0, 1] == pytest.approx(1.0)
    assert matrix[0, 2] == pytest.approx(1.0)
    assert matrix[1, 2] == pytest.approx(0.75)
    assert np.trace(matrix) == pytest.approx(3.0)
    assert comparable[1, 2] == 4

    step = MsaIdentityMatrixStep()
    ctx = Ctx({"output": "identity"})
    step.run(ctx, [_aligned(sequences)])
    out = ctx["identity"]
    assert list(out.labels["taxon"]) == ["seq0", "seq1", "seq2"]
    exported = step.export(ctx)
    assert exported["min_identity"] == pytest.approx(0.75)
    assert exported["mean_identity"] == pytest.approx((1.0 + 1.0 + 0.75) / 3)


def test_trim_removes_gappy_columns(tmp_path):
    result = trim_alignment(
        ["s1", "s2", "s3"], ["A-GT", "ATGT", "ACGT"], 0.2, 0.5
    )
    assert result["columns_before"] == 4
    assert result["columns_after"] == 3
    assert result["columns_removed"] == 1
    assert result["rows_after"] == 3
    assert result["sequences"] == ["AGT", "AGT", "AGT"]

    step = MsaTrimStep()
    ctx = Ctx({"output": "trimmed", "max_gap_fraction": 0.2}, tmp_path)
    step.run(ctx, [_aligned(["A-GT", "ATGT", "ACGT"])])
    artifact = ctx["trimmed"]
    assert artifact.format == "fasta"
    path = artifact.files["alignment"]
    assert path.startswith(str(tmp_path))
    text = open(path, encoding="utf-8").read()
    assert text.count(">") == 3
    exported = step.export(ctx)
    assert exported["columns_after"] == 3
    assert exported["result_files"][0]["format"] == "fasta"


def test_trim_rejects_alignment_without_usable_columns():
    with pytest.raises(StepError):
        trim_alignment(["s1", "s2"], ["A-", "-A"], 0.0, 0.5)


def test_trim_drops_low_coverage_rows():
    result = trim_alignment(
        ["s1", "s2", "s3"], ["ACGT", "A---", "ACGT"], 1.0, 0.75
    )
    assert result["rows_after"] == 2
    assert result["rows_removed"] == 1
    assert result["names"] == ["s1", "s3"]


def test_detect_alphabet_and_unsupported_characters():
    assert detect_alphabet(["ACGT-", "AC-T"]) == "dna"
    assert detect_alphabet(["ACGU", "AC-U"]) == "rna"
    assert detect_alphabet(["ACGURYSW", "ACGU----"]) == "rna"
    assert detect_alphabet(["ACGTRYSW", "ACGT----"]) == "dna"
    assert detect_alphabet(["ACDE", "AC-E"]) == "protein"
    with pytest.raises(StepError):
        detect_alphabet(["ACGT", "AC?T"])


def test_estimate_memory_accepts_empty_inputs():
    for step_class in (
        MsaColumnStatsStep,
        MsaConsensusStep,
        MsaIdentityMatrixStep,
        MsaTrimStep,
    ):
        workspace, output = step_class.estimate_memory([], {}, {})
        assert workspace > 0
        assert output >= 0
