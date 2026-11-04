"""Tests for rdkit_ring_systems and rdkit_charge_profile."""

from __future__ import annotations

import numpy as np
import pytest
from rdkit import Chem
from rdkit.Chem import AllChem
from src.core.errors import StepError
from src.task.step.steps.rdkit_charge_profile import (
    RdkitChargeProfileStep,
    charge_row,
    gasteiger_charges,
)
from src.task.step.steps.rdkit_ring_systems import (
    RdkitRingSystemsStep,
    ring_row,
    ring_systems,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(step, params):
    ctx = Ctx(params)
    step.run(ctx, [])
    return ctx[ctx.step_params.get("output", "out")], step.export(ctx)


def test_ring_row_hand_values() -> None:
    benzene = Chem.MolFromSmiles("c1ccccc1")
    assert ring_row(benzene) == [1.0, 1.0, 1.0, 0.0, 6.0, 6.0]
    toluene = Chem.MolFromSmiles("Cc1ccccc1")
    assert ring_row(toluene) == [1.0, 1.0, 1.0, 0.0, 6.0, 6.0]
    naphthalene = Chem.MolFromSmiles("c1ccc2ccccc2c1")
    assert ring_row(naphthalene)[:4] == [2.0, 2.0, 1.0, 0.0]
    ethane = Chem.MolFromSmiles("CC")
    assert ring_row(ethane) == [0.0] * 6


def test_ring_row_matches_rdkit_oracle() -> None:
    for smiles in ("c1ccccc1", "c1ccc2ccccc2c1", "C1CCC2(CC1)CCCC2", "O=C1NC=CC(=O)N1"):
        molecule = Chem.MolFromSmiles(smiles)
        rings = molecule.GetRingInfo().AtomRings()
        row = ring_row(molecule)
        assert row[0] == len(rings)
        assert row[4] == max(len(ring) for ring in rings)
        assert row[5] == pytest.approx(float(np.mean([len(ring) for ring in rings])))


def test_ring_systems_spiro_and_fused() -> None:
    spiro = Chem.MolFromSmiles("C1CC12CC2")
    systems, spiro_links = ring_systems(spiro)
    assert systems == 2
    assert spiro_links == 1
    fused = Chem.MolFromSmiles("c1ccc2ccccc2c1")
    assert ring_systems(fused) == (1, 0)
    acyclic = Chem.MolFromSmiles("CCO")
    assert ring_systems(acyclic) == (0, 0)


def test_ring_step_output() -> None:
    out, export = _run(
        RdkitRingSystemsStep(), {"smiles": "c1ccccc1 benzene\nCC ethane"}
    )
    assert out.dims == ["molecule", "statistic"]
    assert out.data.shape == (2, 6)
    assert list(out.labels["molecule"].keys()) == ["benzene", "ethane"]
    assert export["total_rings"] == 1
    assert export["molecules_with_rings"] == 1


def test_ring_step_errors() -> None:
    with pytest.raises(StepError, match="smiles is required"):
        _run(RdkitRingSystemsStep(), {"smiles": ""})
    with pytest.raises(StepError, match="cannot parse SMILES"):
        _run(RdkitRingSystemsStep(), {"smiles": "notasmiles"})


def test_charge_row_hand_values() -> None:
    sodium = Chem.MolFromSmiles("[Na+]")
    row = charge_row(sodium)
    assert row[0] == 1.0
    assert row[1] == 1.0
    assert row[2] == 0.0
    acetate = Chem.MolFromSmiles("CC(=O)[O-]")
    row = charge_row(acetate)
    assert row[0] == -1.0
    assert row[1] == 0.0
    assert row[2] == 1.0
    ethanol = Chem.MolFromSmiles("CCO")
    assert charge_row(ethanol)[0] == 0.0


def test_charge_row_matches_rdkit_oracle() -> None:
    for smiles in ("CCO", "CC(=O)[O-]", "c1ccccc1", "C[N+](C)(C)C"):
        molecule = Chem.MolFromSmiles(smiles)
        probe = Chem.Mol(molecule)
        AllChem.ComputeGasteigerCharges(probe)
        expected = np.asarray(
            [
                atom.GetDoubleProp("_GasteigerCharge")
                for atom in probe.GetAtoms()
                if atom.GetAtomicNum() > 1
            ],
            dtype=float,
        )
        row = charge_row(molecule)
        assert row[3] == pytest.approx(float(expected.sum()), abs=1e-9)
        assert row[4] == pytest.approx(float(np.mean(np.abs(expected))), abs=1e-9)
        assert row[5] == pytest.approx(float(expected.max()), abs=1e-9)
        assert row[6] == pytest.approx(float(expected.min()), abs=1e-9)
    assert len(gasteiger_charges(Chem.MolFromSmiles("CCO"))) == 3


def test_charge_step_output_and_errors() -> None:
    out, export = _run(
        RdkitChargeProfileStep(), {"smiles": "CCO ethanol\nCC(=O)[O-] acetate"}
    )
    assert out.data.shape == (2, 7)
    assert out.data[0, 0] == 0.0
    assert out.data[1, 0] == -1.0
    assert export["neutral_molecules"] == 1
    assert export["charged_molecules"] == 1
    with pytest.raises(StepError, match="smiles is required"):
        _run(RdkitChargeProfileStep(), {"smiles": "   "})
