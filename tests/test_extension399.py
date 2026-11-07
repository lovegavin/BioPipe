"""Contract tests for RNA secondary-structure comparison operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps import _rna_structure_utils as rna
from src.task.step.steps.rna_structure_consensus import RnaStructureConsensusStep
from src.task.step.steps.rna_structure_distance import RnaStructureDistanceStep
from src.task.step.steps.rna_structure_features import RnaStructureFeaturesStep


def sequence_form(names, sequences):
    alphabet = {"A": 0, "C": 1, "G": 2, "U": 3, "N": 4}
    width = max(len(item) for item in sequences)
    unknown = 5
    data = np.full((len(sequences), width), float(unknown), dtype=np.float32)
    for row, sequence in enumerate(sequences):
        for col, char in enumerate(sequence):
            data[row, col] = alphabet.get(char, unknown)
    labels = {
        "sequence": {name: index for index, name in enumerate(names)},
        "position": {str(index): index for index in range(width)},
    }
    return Form(
        data=data,
        dims=["sequence", "position"],
        labels=labels,
        info={"representation": "sequence_codes", "alphabet": "rna", "alphabet_map": alphabet,
              "unknown_code": unknown, "missing_code": np.nan},
    )


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def run_step(step, form, params):
    ctx = Ctx(params)
    step.name = step.definition["id"]
    step.run(ctx, [form])
    return ctx


def test_clean_rna_normalises_and_rejects():
    assert rna.clean_rna("acgut", "t") == "ACGUU"
    with pytest.raises(StepError, match="non-nucleotide"):
        rna.clean_rna("ACGX", "t")


def test_base_pair_distance_and_hamming():
    left = "((....))"
    right = "((...).)"
    assert rna.base_pair_distance(left, right, "t") == 2
    assert rna.hamming_distance(left, right, "t") == 2
    with pytest.raises(StepError, match="same length"):
        rna.hamming_distance("(..)", "(....)", "t")


def test_structure_features_hairpin_and_stem():
    features = rna.structure_features("((...))", "t")
    assert features["n_pairs"] == 2
    assert features["n_stems"] == 1
    assert features["max_stem_length"] == 2
    assert features["n_hairpins"] == 1
    assert features["n_stacked_pairs"] == 1
    assert features["n_unpaired"] == 3


def test_unbalanced_structure_is_rejected():
    with pytest.raises(StepError, match="balanced"):
        rna.structure_features("((...)", "t")


def test_fold_structures_parses_rnafold_output(monkeypatch):
    class Completed:
        returncode = 0
        stdout = ">trna01\nACGUACGU\n((....)) (-1.00)\n"
        stderr = ""

    monkeypatch.setattr(rna.subprocess, "run", lambda *args, **kwargs: Completed())
    assert rna.fold_structures(["ACGUACGU"]) == ["((....))"]


def test_subopt_structures_parses_groups(monkeypatch):
    class Completed:
        returncode = 0
        stdout = ">s1 [3]\nACGUACGU\n((....)) -1.0\n(......) -0.5\n"
        stderr = ""

    monkeypatch.setattr(rna.subprocess, "run", lambda *args, **kwargs: Completed())
    assert rna.subopt_structures(["ACGUACGU"]) == [["((....))", "(......)"]]


def test_distance_operator_two_temperatures(monkeypatch):
    import src.task.step.steps.rna_structure_distance as module

    def fake_fold(sequences, *, binary, temperature, dangles, timeout):
        return ["((....))"] * len(sequences) if temperature == 37.0 else ["((...).)"] * len(sequences)

    monkeypatch.setattr(module, "fold_structures", fake_fold)
    form = sequence_form(["a"], ["ACGUACGU"])
    ctx = run_step(RnaStructureDistanceStep(), form,
                   {"temperature_a": 37.0, "temperature_b": 50.0, "output": "dist"})
    result = ctx["dist"]
    assert result.dims == ["pair", "statistic"]
    row = result.data[0]
    assert row[0] == 2
    assert row[1] == 1
    assert row[2] == 3
    assert row[3] == 2
    assert row[4] == pytest.approx(2.0 / 3.0)


def test_distance_operator_rejects_equal_temperatures():
    form = sequence_form(["a"], ["ACGU"])
    with pytest.raises(StepError, match="must differ"):
        run_step(RnaStructureDistanceStep(), form, {"temperature_a": 37.0, "temperature_b": 37.0})


def test_consensus_operator_picks_majority_pairs(monkeypatch):
    import src.task.step.steps.rna_structure_consensus as module

    def fake_subopt(sequences, *, binary, temperature, energy_window, max_structures, timeout):
        return [["((....))", "((....))", "(.(...))"] for _ in sequences]

    def fake_fold(sequences, *, binary, temperature, timeout):
        return ["((....))" for _ in sequences]

    monkeypatch.setattr(module, "subopt_structures", fake_subopt)
    monkeypatch.setattr(module, "fold_structures", fake_fold)
    form = sequence_form(["a"], ["ACGUACGU"])
    ctx = run_step(RnaStructureConsensusStep(), form, {"threshold": 0.5, "output": "cons"})
    result = ctx["cons"]
    assert result.info["consensus"] == ["((....))"]
    row = result.data[0]
    assert row[0] == 3
    assert row[1] == 2
    assert row[2] == pytest.approx(5.0 / 6.0)
    assert row[3] == pytest.approx(0.5)
    assert row[4] == 0
