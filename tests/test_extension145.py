"""Tests for the RDKit oral-bioavailability and QED operators."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps.rdkit_oral_bioavailability import (
    RdkitOralBioavailabilityStep,
    bioavailability_row,
)
from src.task.step.steps.rdkit_qed import RdkitQedStep, qed_row

rdkit = pytest.importorskip("rdkit")
from rdkit import Chem  # noqa: E402
from rdkit.Chem import Descriptors, QED  # noqa: E402


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.written_outputs = set()

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.written_outputs.add(key)


def _run(step, params):
    ctx = Ctx(params)
    step.run(ctx, [])
    return ctx[params.get("output", "out")], step.export(ctx)


def _molecule(smiles):
    molecule = Chem.MolFromSmiles(smiles)
    assert molecule is not None
    return molecule


def test_qed_row_matches_rdkit() -> None:
    for smiles in ("CCO", "c1ccccc1", "CC(=O)Oc1ccccc1C(=O)O"):
        molecule = _molecule(smiles)
        row = qed_row(molecule)
        assert row["qed"] == pytest.approx(QED.qed(molecule), rel=1e-9)
        assert row["molecular_weight"] == pytest.approx(Descriptors.MolWt(molecule))
    assert qed_row(_molecule("CCO"))["qed"] == pytest.approx(0.4068, abs=5e-4)


def test_qed_step_output() -> None:
    step = RdkitQedStep()
    out, exported = _run(step, {"smiles": "CCO ethanol\nc1ccccc1 benzene"})
    assert out.dims == ["molecule", "statistic"]
    assert list(out.labels["molecule"]) == ["ethanol", "benzene"]
    assert out.data.shape == (2, 8)
    assert list(out.labels["statistic"]) == [
        "qed",
        "molecular_weight",
        "mol_logp",
        "tpsa",
        "h_donors",
        "h_acceptors",
        "rotatable_bonds",
        "aromatic_rings",
    ]
    assert out.data[0, 0] == pytest.approx(0.4068, abs=5e-4)
    assert out.data[1, 7] == pytest.approx(1.0)
    assert exported["n_molecules"] == 2
    assert exported["molecules"][1]["qed"] == pytest.approx(0.4426, abs=5e-4)


def test_qed_errors() -> None:
    with pytest.raises(StepError, match="smiles must contain at least one SMILES line"):
        _run(RdkitQedStep(), {"smiles": "   \n# comment"})
    with pytest.raises(StepError, match="cannot parse SMILES"):
        _run(RdkitQedStep(), {"smiles": "notasmiles"})


def test_bioavailability_row_hand_values() -> None:
    ethanol = bioavailability_row(_molecule("CCO"))
    assert ethanol["molecular_weight"] == pytest.approx(46.069, abs=1e-3)
    assert ethanol["mol_logp"] == pytest.approx(-0.0014, abs=1e-3)
    assert ethanol["tpsa"] == pytest.approx(20.23, abs=0.01)
    assert ethanol["h_donors"] == 1.0
    assert ethanol["h_acceptors"] == 1.0
    assert ethanol["n_lipinski_violations"] == 0.0
    assert ethanol["oral_bioavailability_pass"] == 1.0

    benzene = bioavailability_row(_molecule("c1ccccc1"))
    assert benzene["tpsa"] == 0.0
    assert benzene["egan_pass"] == 1.0


def test_bioavailability_violations_and_thresholds() -> None:
    long_chain = bioavailability_row(_molecule("C" * 40))
    assert long_chain["molecular_weight"] > 500.0
    assert long_chain["mol_logp"] > 5.0
    assert long_chain["n_lipinski_violations"] >= 2
    assert long_chain["lipinski_pass"] == 0.0
    assert long_chain["egan_pass"] == 0.0
    assert long_chain["oral_bioavailability_pass"] == 0.0

    # One violation is still accepted by the common "at most one failure" rule.
    custom = bioavailability_row(_molecule("c1ccccc1"), mw_max=70.0)
    assert custom["n_lipinski_violations"] == 1
    assert custom["lipinski_pass"] == 1.0
    two = bioavailability_row(_molecule("c1ccccc1"), mw_max=70.0, logp_max=1.0)
    assert two["n_lipinski_violations"] == 2
    assert two["lipinski_pass"] == 0.0


def test_bioavailability_step_output() -> None:
    step = RdkitOralBioavailabilityStep()
    out, exported = _run(
        step, {"smiles": "CCO ethanol\nc1ccccc1 benzene", "output": "bio"}
    )
    assert out.dims == ["molecule", "statistic"]
    assert list(out.labels["molecule"]) == ["ethanol", "benzene"]
    assert out.data.shape == (2, 11)
    assert list(out.labels["statistic"])[10] == "oral_bioavailability_pass"
    assert np.all(out.data[:, 10] == 1.0)
    assert out.info["rule_sets"] == ["lipinski", "veber", "egan"]
    assert out.info["thresholds"]["egan_tpsa_max"] == 131.6
    assert exported["n_passing"] == 2


def test_bioavailability_errors() -> None:
    with pytest.raises(StepError, match="smiles must contain at least one SMILES line"):
        _run(RdkitOralBioavailabilityStep(), {"smiles": ""})
    with pytest.raises(StepError, match="cannot parse SMILES"):
        _run(RdkitOralBioavailabilityStep(), {"smiles": "C1CC"})
    with pytest.raises(StepError, match="without heavy atoms"):
        _run(RdkitQedStep(), {"smiles": "[H][H]"})
