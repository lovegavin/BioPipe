"""Tests for rdkit_admet_rules and rdkit_conformer_energy."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import StepError
from src.task.step.steps.rdkit_admet_rules import (
    _STATISTICS as ADMET_STATISTICS,
    RdkitAdmetRulesStep,
)
from src.task.step.steps.rdkit_conformer_energy import (
    _FORCE_FIELDS,
    _STATISTICS as ENERGY_STATISTICS,
    RdkitConformerEnergyStep,
)

rdkit = pytest.importorskip("rdkit")
from rdkit import Chem  # noqa: E402
from rdkit.Chem import AllChem, Crippen, Descriptors, Lipinski, rdMolDescriptors  # noqa: E402


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(step, params):
    ctx = Ctx(params)
    step.run(ctx, [])
    return ctx["out"], step.export(ctx)


def _values(form, row, name):
    position = form.labels["statistic"][name]
    return float(form.data[row, position])


def test_admet_descriptors_match_rdkit():
    form, export = _run(RdkitAdmetRulesStep(), {"smiles": "CCO ethanol"})
    molecule = Chem.MolFromSmiles("CCO")
    expected = {
        "molecular_weight": Descriptors.MolWt(molecule),
        "mol_logp": Crippen.MolLogP(molecule),
        "tpsa": rdMolDescriptors.CalcTPSA(molecule),
        "h_donors": Lipinski.NumHDonors(molecule),
        "h_acceptors": Lipinski.NumHAcceptors(molecule),
        "rotatable_bonds": Lipinski.NumRotatableBonds(molecule),
        "ring_count": rdMolDescriptors.CalcNumRings(molecule),
    }
    assert form.dims == ["molecule", "statistic"]
    assert form.labels["molecule"] == {"ethanol": 0}
    assert list(form.labels["statistic"]) == list(ADMET_STATISTICS)
    for name, value in expected.items():
        np.testing.assert_allclose(
            _values(form, 0, name), float(value), rtol=1e-5, atol=1e-5, err_msg=name
        )
    assert _values(form, 0, "lipinski_violations") == 0
    assert _values(form, 0, "veber_pass") == 1
    assert _values(form, 0, "ghose_pass") == 0  # only 3 heavy atoms
    assert export["passing_lipinski"] == 1


def test_admet_rule_flags_for_aspirin_and_decane():
    form, export = _run(
        RdkitAdmetRulesStep(),
        {"smiles": "CC(=O)Oc1ccccc1C(=O)O aspirin\nCCCCCCCCCCCCCCCCCCCC decane"},
    )
    assert form.labels["molecule"] == {"aspirin": 0, "decane": 1}
    assert _values(form, 0, "lipinski_violations") == 0
    assert _values(form, 0, "veber_pass") == 1
    assert _values(form, 0, "ghose_pass") == 0
    assert _values(form, 1, "mol_logp") > 5
    assert _values(form, 1, "lipinski_violations") == 1
    assert export == {
        "n_molecules": 2,
        "passing_lipinski": 1,
        "passing_veber": 1,
        "passing_ghose": 0,
        "statistics": list(ADMET_STATISTICS),
    }


def test_admet_custom_thresholds():
    form, _export = _run(
        RdkitAdmetRulesStep(),
        {"smiles": "CCO ethanol", "mw_max": 40, "hbd_max": 0},
    )
    assert _values(form, 0, "lipinski_violations") == 2


def test_admet_errors():
    with pytest.raises(StepError, match="smiles is required"):
        _run(RdkitAdmetRulesStep(), {})
    with pytest.raises(StepError, match="mw_max must be positive"):
        _run(RdkitAdmetRulesStep(), {"smiles": "CCO", "mw_max": 0})
    with pytest.raises(StepError, match="must not be negative"):
        _run(RdkitAdmetRulesStep(), {"smiles": "CCO", "hbd_max": -1})
    with pytest.raises(StepError, match="must contain at least one SMILES"):
        _run(RdkitAdmetRulesStep(), {"smiles": "# only a comment"})
    with pytest.raises(StepError, match="cannot parse"):
        _run(RdkitAdmetRulesStep(), {"smiles": "not-a-molecule bad"})


def test_conformer_energies_are_deterministic_and_finite():
    params = {"smiles": "CCCCCC hexane", "num_conformers": 3, "force_field": "MMFF94"}
    first, export = _run(RdkitConformerEnergyStep(), params)
    second, _export = _run(RdkitConformerEnergyStep(), params)
    assert first.dims == ["molecule", "statistic"]
    assert list(first.labels["statistic"]) == list(ENERGY_STATISTICS)
    assert first.labels["molecule"] == {"hexane": 0}
    np.testing.assert_allclose(first.data, second.data, rtol=0, atol=0)
    energy = _values(first, 0, "min_energy")
    assert np.isfinite(energy)
    assert 1 <= _values(first, 0, "n_conformers") <= 3
    stored = first.info["conformer_energies"][0]
    assert len(stored) == int(_values(first, 0, "n_conformers"))
    assert _values(first, 0, "energy_spread") >= 0
    assert _values(first, 0, "minimized") == 1
    np.testing.assert_allclose(_values(first, 0, "min_energy"), min(stored), rtol=1e-5)
    np.testing.assert_allclose(_values(first, 0, "mean_energy"), np.mean(stored), rtol=1e-5)
    assert export["force_field"] == "MMFF94"


def test_benzene_has_a_single_symmetric_conformer():
    form, _export = _run(
        RdkitConformerEnergyStep(), {"smiles": "c1ccccc1 benzene", "num_conformers": 2}
    )
    assert _values(form, 0, "n_conformers") == 1
    assert _values(form, 0, "energy_spread") == 0


def test_conformer_energy_matches_rdkit_minimization():
    molecule = Chem.AddHs(Chem.MolFromSmiles("CCO"))
    embedding = AllChem.ETKDGv3()
    embedding.randomSeed = 20240517
    embedding.pruneRmsThresh = 0.25
    embedding.numThreads = 1
    conf_ids = list(AllChem.EmbedMultipleConfs(molecule, numConfs=1, params=embedding))
    properties = AllChem.MMFFGetMoleculeProperties(molecule, mmffVariant="MMFF94")
    force = AllChem.MMFFGetMoleculeForceField(molecule, properties, confId=int(conf_ids[0]))
    force.Minimize(maxIts=500)
    reference = float(force.CalcEnergy())
    form, _export = _run(
        RdkitConformerEnergyStep(), {"smiles": "CCO ethanol", "num_conformers": 1}
    )
    np.testing.assert_allclose(_values(form, 0, "min_energy"), reference, rtol=1e-4, atol=1e-3)


def test_methane_energy_is_near_zero():
    form, _export = _run(RdkitConformerEnergyStep(), {"smiles": "C methane", "num_conformers": 1})
    assert abs(_values(form, 0, "min_energy")) < 1.0


def test_uff_force_field_runs():
    assert "UFF" in _FORCE_FIELDS
    form, export = _run(
        RdkitConformerEnergyStep(),
        {"smiles": "CCO ethanol", "num_conformers": 2, "force_field": "UFF"},
    )
    assert np.isfinite(_values(form, 0, "min_energy"))
    assert export["force_field"] == "UFF"


def test_conformer_errors():
    with pytest.raises(StepError, match="smiles is required"):
        _run(RdkitConformerEnergyStep(), {})
    with pytest.raises(StepError, match="force_field must be one of"):
        _run(RdkitConformerEnergyStep(), {"smiles": "CCO", "force_field": "MMFF"})
    with pytest.raises(StepError, match="num_conformers must be between"):
        _run(RdkitConformerEnergyStep(), {"smiles": "CCO", "num_conformers": 0})
    with pytest.raises(StepError, match="max_iterations must be between"):
        _run(RdkitConformerEnergyStep(), {"smiles": "CCO", "max_iterations": 0})
