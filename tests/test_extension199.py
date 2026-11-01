"""Tests for rdkit_reaction_smarts_apply."""

from __future__ import annotations

import pytest

rdkit = pytest.importorskip("rdkit")

from rdkit import Chem  # noqa: E402
from rdkit.Chem import AllChem  # noqa: E402

from src.core.errors import StepError  # noqa: E402
from src.task.step.steps.rdkit_reaction_smarts_apply import (  # noqa: E402
    RdkitReactionSmartsApplyStep,
    product_smiles,
    reaction_from_smarts,
)

REACTION = "[CH3:1][O:2][c:3]>>[O:2][c:3]"


class Ctx(dict):
    def __init__(self, params: dict) -> None:
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def test_product_matches_rdkit() -> None:
    reaction = reaction_from_smarts(REACTION)
    anisole = Chem.MolFromSmiles("COc1ccccc1")
    products = product_smiles(reaction, anisole, 10)
    assert products == [Chem.MolToSmiles(Chem.MolFromSmiles("Oc1ccccc1"))]


def test_step_output() -> None:
    ctx = Ctx({"output": "out", "smiles": "COc1ccccc1\nc1ccccc1\n", "reaction_smarts": REACTION})
    step = RdkitReactionSmartsApplyStep()
    step.run(ctx, [])
    out = ctx["out"]
    assert out.data.shape == (2, 3)
    assert list(out.labels["statistic"]) == [
        "n_reactant_matches", "n_products", "mean_product_heavy_atoms"
    ]
    assert out.data[0, 0] == pytest.approx(1.0)
    assert out.data[0, 1] == pytest.approx(1.0)
    assert out.data[0, 2] == pytest.approx(7.0)
    assert out.data[1, 1] == pytest.approx(0.0)
    assert out.info["molecules"][0]["products"] == ["Oc1ccccc1"]
    assert step.export(ctx)["n_with_products"] == 1


def test_errors() -> None:
    step = RdkitReactionSmartsApplyStep()
    with pytest.raises(StepError, match="reaction_smarts is required"):
        step.run(Ctx({"output": "out", "smiles": "CCO", "reaction_smarts": ""}), [])
    with pytest.raises(StepError, match="cannot parse reaction_smarts"):
        step.run(Ctx({"output": "out", "smiles": "CCO", "reaction_smarts": "not a reaction"}), [])
    with pytest.raises(StepError, match="must contain at least one SMILES"):
        step.run(Ctx({"output": "out", "smiles": "", "reaction_smarts": REACTION}), [])
    with pytest.raises(StepError, match="max_products must be positive"):
        step.run(Ctx({"output": "out", "smiles": "CCO", "reaction_smarts": REACTION, "max_products": 0}), [])
    with pytest.raises(StepError, match="cannot parse SMILES"):
        step.run(Ctx({"output": "out", "smiles": "notasmiles", "reaction_smarts": REACTION}), [])


def test_reaction_from_smarts_returns_object() -> None:
    reaction = reaction_from_smarts(REACTION)
    assert isinstance(reaction, AllChem.ChemicalReaction)
