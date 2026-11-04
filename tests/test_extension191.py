from __future__ import annotations

import numpy as np
import pytest
from rdkit import Chem

from src.core.errors import StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.rdkit_scaffold_diversity import (
    RdkitScaffoldDiversityStep,
    diversity_rows,
    scaffold_profile,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def test_scaffold_profile_strips_substituents() -> None:
    assert scaffold_profile(Chem.MolFromSmiles("c1ccccc1C"))[0] == "c1ccccc1"
    assert scaffold_profile(Chem.MolFromSmiles("CCO"))[0] == "acyclic"
    assert scaffold_profile(Chem.MolFromSmiles("CCO"))[1] == 0


def test_diversity_rows_groups_by_scaffold() -> None:
    molecules = [
        Chem.MolFromSmiles("c1ccccc1"),
        Chem.MolFromSmiles("c1ccccc1C"),
        Chem.MolFromSmiles("CCO"),
    ]
    rows = diversity_rows(molecules)
    assert rows[0]["scaffold"] == "c1ccccc1"
    assert rows[0]["n_molecules"] == 2
    assert rows[0]["fraction"] == pytest.approx(2 / 3)
    assert rows[1]["scaffold"] == "acyclic"
    assert rows[1]["mean_scaffold_atoms"] == pytest.approx(0.0)


def test_step_output_matches_rdkit_oracle() -> None:
    smiles = "c1ccccc1 benzene\nc1ccccc1C toluene\nCCO ethanol\n"
    step = RdkitScaffoldDiversityStep()
    ctx = Ctx({"smiles": smiles})
    step.run(ctx, [])
    out = ctx["out"]
    assert list(out.dims) == ["scaffold", "statistic"]
    assert list(out.labels["scaffold"].keys()) == ["c1ccccc1", "acyclic"]
    assert out.data[0].tolist() == pytest.approx([2.0, 2 / 3, 6.0])
    assert out.data[1].tolist() == pytest.approx([1.0, 1 / 3, 0.0])
    from rdkit.Chem.Scaffolds import MurckoScaffold

    oracle = {}
    for name, text in [("a", "c1ccccc1"), ("b", "c1ccccc1C"), ("c", "CCO")]:
        scaffold = MurckoScaffold.GetScaffoldForMol(Chem.MolFromSmiles(text))
        key = Chem.MolToSmiles(scaffold) if scaffold.GetNumHeavyAtoms() else "acyclic"
        oracle[key] = oracle.get(key, 0) + 1
    assert oracle == {"c1ccccc1": 2, "acyclic": 1}
    assert step._export_data["n_scaffolds"] == 2
    assert step._export_data["scaffold_ratio"] == pytest.approx(2 / 3)


def test_errors() -> None:
    with pytest.raises(StepError, match="at least one SMILES line"):
        RdkitScaffoldDiversityStep().run(Ctx({"smiles": ""}), [])
    with pytest.raises(StepError, match="cannot parse"):
        RdkitScaffoldDiversityStep().run(Ctx({"smiles": "notasmiles"}), [])
