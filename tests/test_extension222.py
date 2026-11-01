"""Tests for the Murcko scaffold tree operator."""

from __future__ import annotations

import pytest

from src.core.errors import StepError
from src.task.step.steps.rdkit_scaffold_tree import RdkitScaffoldTreeStep, scaffold_chain, tree_rows

rdkit = pytest.importorskip("rdkit")
from rdkit import Chem  # noqa: E402


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "scaffolds", **params}
        self.metadata = {}


def _run(params, *, output="scaffolds"):
    step = RdkitScaffoldTreeStep()
    ctx = Ctx({**params, "output": output})
    step.run(ctx, [])
    return ctx[output], step.export(ctx)


def test_scaffold_chain_benzene_and_aspirin() -> None:
    benzene = Chem.MolFromSmiles("c1ccccc1")
    aspirin = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
    assert scaffold_chain(benzene, 3) == ["c1ccccc1"]
    assert scaffold_chain(aspirin, 3) == ["c1ccccc1"]
    naphthalene = scaffold_chain(Chem.MolFromSmiles("c1ccc2ccccc2c1"), 3)
    assert naphthalene == ["c1ccc2ccccc2c1"]


def test_tree_rows_groups_shared_scaffold() -> None:
    molecules = [
        ("benzene", Chem.MolFromSmiles("c1ccccc1")),
        ("toluene", Chem.MolFromSmiles("Cc1ccccc1")),
        ("aspirin", Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")),
        ("naphthalene", Chem.MolFromSmiles("c1ccc2ccccc2c1")),
    ]
    rows = tree_rows(molecules, 3)
    assert rows[0][0] == "c1ccccc1"
    assert rows[0][1:] == (1, 3, 6, 6)
    assert rows[1][0] == "c1ccc2ccccc2c1"
    assert rows[1][1:] == (1, 1, 10, 11)


def test_step_output_and_export() -> None:
    smiles = "c1ccccc1 benzene\nCc1ccccc1 toluene\nCC(=O)Oc1ccccc1C(=O)O aspirin"
    out, export = _run({"smiles": smiles, "max_level": 2})
    assert out.data.shape == (1, 4)
    assert list(out.labels["scaffold"]) == ["c1ccccc1"]
    assert out.data[0].tolist() == [1.0, 3.0, 6.0, 6.0]
    assert export["n_molecules"] == 3
    assert out.info["n_nodes"] == 1


def test_parameter_errors() -> None:
    with pytest.raises(StepError, match="smiles is required"):
        _run({})
    with pytest.raises(StepError, match="max_level"):
        _run({"smiles": "c1ccccc1", "max_level": 0})
    with pytest.raises(StepError, match="max_level"):
        _run({"smiles": "c1ccccc1", "max_level": 6})
    with pytest.raises(StepError, match="max_level"):
        _run({"smiles": "c1ccccc1", "max_level": 2.5})
    with pytest.raises(StepError, match="no molecule"):
        _run({"smiles": "CCO"})
