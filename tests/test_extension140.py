"""Tests for the RDKit ESOL solubility operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps.rdkit_esol import RdkitEsolStep, esol_row


class _Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "solubility", **params}
        self.metadata = {}


def _run(params):
    ctx = _Ctx(params)
    step = RdkitEsolStep()
    step.run(ctx, [])
    return ctx[params.get("output", "solubility")], step.export(ctx)


def test_ethanol_matches_hand_computation() -> None:
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors, Lipinski

    molecule = Chem.MolFromSmiles("CCO")
    row = esol_row(molecule)
    expected_log = (
        0.16
        - 0.63 * Crippen.MolLogP(molecule)
        - 0.0062 * Descriptors.MolWt(molecule)
        + 0.066 * Lipinski.NumRotatableBonds(molecule)
        - 0.74 * 0.0
    )
    assert row["esol_log_molar"] == pytest.approx(expected_log, abs=1e-9)
    assert row["aromatic_proportion"] == 0.0
    assert row["esol_solubility_mg_l"] == pytest.approx(
        10**expected_log * Descriptors.MolWt(molecule) * 1000.0, rel=1e-6
    )
    assert row["molecular_weight"] == pytest.approx(46.069, abs=1e-3)


def test_benzene_aromatic_proportion_is_one() -> None:
    from rdkit import Chem

    row = esol_row(Chem.MolFromSmiles("c1ccccc1"))
    assert row["aromatic_atoms"] == 6.0
    assert row["heavy_atoms"] == 6.0
    assert row["aromatic_proportion"] == pytest.approx(1.0)
    assert row["esol_log_molar"] == pytest.approx(
        0.16 - 0.63 * 1.6866 - 0.0062 * 78.114 - 0.74, abs=2e-3
    )


def test_step_output_matches_rdkit_recomputation() -> None:
    from rdkit import Chem
    from rdkit.Chem import Crippen, Descriptors, Lipinski

    smiles = "CCO ethanol\nc1ccccc1 benzene\nCC(=O)Oc1ccccc1C(=O)O aspirin"
    form, exported = _run({"smiles": smiles})
    assert form.data.shape == (3, 8)
    assert list(form.labels["molecule"]) == ["ethanol", "benzene", "aspirin"]
    assert form.labels["statistic"]["esol_log_molar"] == 6
    for index, name in enumerate(("CCO", "c1ccccc1", "CC(=O)Oc1ccccc1C(=O)O")):
        molecule = Chem.MolFromSmiles(name)
        expected = (
            0.16
            - 0.63 * Crippen.MolLogP(molecule)
            - 0.0062 * Descriptors.MolWt(molecule)
            + 0.066 * Lipinski.NumRotatableBonds(molecule)
            - 0.74 * sum(1 for atom in molecule.GetAtoms() if atom.GetIsAromatic()) / molecule.GetNumHeavyAtoms()
        )
        assert form.data[index, 6] == pytest.approx(expected, abs=1e-5)
    assert exported["n_molecules"] == 3
    assert exported["mean_log_solubility"] == pytest.approx(float(form.data[:, 6].mean()), abs=1e-6)
    assert form.info["model"] == "delaney-esol"


def test_custom_names_and_blank_lines() -> None:
    form, _ = _run({"smiles": "\nCCO\n\n"})
    assert list(form.labels["molecule"]) == ["mol1"]
    assert form.data.shape == (1, 8)


def test_empty_smiles_is_rejected() -> None:
    with pytest.raises(StepError, match="smiles must contain at least one SMILES line"):
        _run({"smiles": ""})


def test_unparseable_smiles_is_rejected() -> None:
    with pytest.raises(StepError, match="cannot parse SMILES"):
        _run({"smiles": "notasmiles"})


def test_dimension_names_are_configurable() -> None:
    form, _ = _run({"smiles": "CCO", "molecule_dim": "compound", "output": "sol"})
    assert list(form.dims) == ["compound", "statistic"]
    assert form.labels["compound"] == {"mol1": 0}
