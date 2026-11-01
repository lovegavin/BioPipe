import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.sequence_orf_finder import (
    STATISTICS,
    SequenceOrfFinderStep,
    find_orfs,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(sequences):
    return encode_sequences(list(sequences), "sequence", "position", "dna")


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return ctx["out"], step.export(ctx)


def test_forward_orf_hand_values():
    sequence = "ATGAAATTTGGGCCCTAATAG"  # start + 5 codons + stop in frame +1
    orfs = find_orfs(sequence, 3, True)
    labels = {(row["frame"], row["start"]) for row in orfs}
    assert ("+1", 1.0) in labels
    forward = [row for row in orfs if row["frame"] == "+1" and row["start"] == 1.0]
    assert len(forward) == 1
    assert forward[0]["length"] == 15.0  # stop TAA is at offset 15
    assert forward[0]["has_stop"] == 1.0


def test_min_length_and_require_start():
    sequence = "TATGAAATTTGGGCCCTAA"
    with_start = find_orfs(sequence, 6, True)
    without = find_orfs(sequence, 6, False)
    assert all(row["length"] >= 6 for row in without)
    assert len(without) >= len(with_start)


def test_reverse_strand():
    forward = "ATGAAACCCTAA"
    reverse = forward
    complement = "".join({"A": "T", "T": "A", "C": "G", "G": "C"}[base] for base in reversed(reverse))
    orfs = find_orfs(complement, 6, True)
    # the reverse-complement of `complement` is `forward`, so the ORF is on the minus strand
    assert any(row["frame"].startswith("-") for row in orfs)


def test_step_columns_and_info():
    form = _form(["ATGAAATTTGGGCCCTAATAG"])
    out, export = _run(SequenceOrfFinderStep(), {"min_length": 6}, form)
    assert list(out.dims) == ["orf", "statistic"]
    labels = [name for name, _ in sorted(out.labels["statistic"].items(), key=lambda item: item[1])]
    assert labels == list(STATISTICS)
    assert out.data.shape[1] == 6
    assert out.info["n_orfs"] >= 1
    assert out.info["orfs"][0]["protein"].startswith("ATG")
    assert export["n_orfs"] >= 1


def test_parameter_errors():
    form = _form(["ATGAAATTTGGGCCCTAATAG"])
    with pytest.raises(StepError, match="min_length"):
        _run(SequenceOrfFinderStep(), {"min_length": 2}, form)
    with pytest.raises(StepError, match="no open reading frame"):
        _run(SequenceOrfFinderStep(), {"min_length": 500}, form)
    with pytest.raises(StepError, match="is required"):
        _run(SequenceOrfFinderStep(), {"position_dim": "other"}, form)

    protein_form = encode_sequences(["MKWV"], "sequence", "position", "protein")
    with pytest.raises(StepError, match="non-nucleotide"):
        _run(SequenceOrfFinderStep(), {"min_length": 3}, protein_form)
