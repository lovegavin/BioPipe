"""Bemis-Murcko scaffold operator (v1.21.0)."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import StepError
from src.task.step.steps.rdkit_scaffold import RdkitScaffoldStep

CHEM = pytest.importorskip("rdkit.Chem")

SMILES = """CCO ethanol
c1ccccc1CC ethylbenzene
CC(=O)Oc1ccccc1C(=O)O aspirin
c1ccc2[nH]ccc2c1 indole"""


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(text, params=None):
    step = RdkitScaffoldStep()
    ctx = Ctx({"smiles": text, **(params or {})})
    step.run(ctx, [])
    return ctx["out"], step.export(ctx)


def test_scaffold_matches_rdkit_oracle():
    from rdkit.Chem.Scaffolds import MurckoScaffold

    form, export = _run(SMILES)
    records = [line.split() for line in SMILES.splitlines()]
    names = [record[1] for record in records]
    assert list(form.labels["molecule"]) == names
    assert form.dims == ["molecule", "statistic"]
    statistics = list(form.labels["statistic"])
    assert statistics == [
        "scaffold_atoms",
        "scaffold_bonds",
        "ring_count",
        "aromatic_ring_count",
        "side_chain_atoms",
    ]

    for row, (smiles, name) in enumerate(records):
        molecule = CHEM.MolFromSmiles(smiles)
        scaffold = MurckoScaffold.GetScaffoldForMol(molecule)
        assert form.info["scaffold_smiles"][row] == CHEM.MolToSmiles(scaffold)
        assert form.data[row, 0] == pytest.approx(scaffold.GetNumAtoms(), abs=0)
        assert form.data[row, 1] == pytest.approx(scaffold.GetNumBonds(), abs=0)
        assert form.data[row, 2] == pytest.approx(
            len(scaffold.GetRingInfo().AtomRings()), abs=0
        )
        assert form.data[row, 4] == pytest.approx(
            molecule.GetNumHeavyAtoms() - scaffold.GetNumAtoms(), abs=0
        )
        assert form.info["input_smiles"][row] == smiles
        assert name in form.labels["molecule"]


def test_hand_computed_benzene_row():
    form, _ = _run("c1ccccc1 benzene")
    # Benzene itself: 6 scaffold atoms, 6 bonds, one aromatic ring, no side chain.
    np.testing.assert_allclose(
        form.data[0], [6.0, 6.0, 1.0, 1.0, 0.0], rtol=0, atol=0
    )


def test_acyclic_molecule_has_empty_scaffold():
    form, _ = _run("CCO ethanol\nCCCC butane")
    assert form.info["scaffold_smiles"] == ["", ""]
    # No scaffold atoms, so every heavy atom counts as a side-chain atom.
    np.testing.assert_allclose(
        form.data, [[0, 0, 0, 0, 3], [0, 0, 0, 0, 4]], rtol=0, atol=0
    )


def test_duplicate_names_are_disambiguated():
    form, _ = _run("CCO lig\nCCN lig")
    assert list(form.labels["molecule"]) == ["lig", "lig#2"]


def test_errors():
    with pytest.raises(StepError, match="at least one SMILES line"):
        _run("   \n# only comments\n")
    with pytest.raises(StepError, match="cannot parse SMILES"):
        _run("C1CC")
    with pytest.raises(StepError, match="smiles is required"):
        _run("")
