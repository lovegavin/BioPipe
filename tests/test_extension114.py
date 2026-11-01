"""RDKit descriptor, fingerprint and standardization operators (v1.20.0)."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import StepError
from src.task.step.steps.rdkit_descriptors import RdkitDescriptorsStep
from src.task.step.steps.rdkit_morgan_fingerprint import (
    RdkitMorganFingerprintStep,
)
from src.task.step.steps.smiles_standardize import SmilesStandardizeStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(step, params):
    ctx = Ctx(params)
    step.run(ctx, [])
    return ctx["out"], step.export(ctx)


def test_descriptors_match_hand_computed_values():
    pytest.importorskip("rdkit")
    step = RdkitDescriptorsStep()
    smiles = (
        "# alkanes, aromatics and an ester\n"
        "CCO ethanol\n"
        "c1ccccc1 benzene\n"
        "CC(=O)Oc1ccccc1C(=O)O aspirin\n"
    )
    form, exported = _run(step, {"smiles": smiles})

    assert form.dims == ["molecule", "descriptor"]
    assert list(form.labels["molecule"]) == ["ethanol", "benzene", "aspirin"]
    assert list(form.labels["descriptor"]) == [
        "molecular_weight",
        "logp",
        "molar_refractivity",
        "tpsa",
        "hbond_donors",
        "hbond_acceptors",
        "rotatable_bonds",
        "ring_count",
        "aromatic_ring_count",
        "heavy_atoms",
        "heteroatoms",
        "fraction_csp3",
    ]
    values = {name: form.data[i] for i, name in enumerate(form.labels["molecule"])}
    ethanol = dict(zip(form.labels["descriptor"], values["ethanol"]))
    benzene = dict(zip(form.labels["descriptor"], values["benzene"]))
    aspirin = dict(zip(form.labels["descriptor"], values["aspirin"]))

    # Hand computation from the RDKit atomic weights: C 12.011, H 1.008, O 15.999.
    assert ethanol["molecular_weight"] == pytest.approx(46.069, abs=1e-2)
    assert benzene["molecular_weight"] == pytest.approx(78.114, abs=1e-2)
    assert aspirin["molecular_weight"] == pytest.approx(180.159, abs=1e-2)
    assert ethanol["heavy_atoms"] == 3
    assert ethanol["heteroatoms"] == 1
    assert ethanol["hbond_donors"] == 1
    assert ethanol["hbond_acceptors"] == 1
    assert ethanol["rotatable_bonds"] == 0
    assert ethanol["ring_count"] == 0
    assert ethanol["fraction_csp3"] == pytest.approx(1.0)
    assert benzene["ring_count"] == 1
    assert benzene["aromatic_ring_count"] == 1
    assert benzene["fraction_csp3"] == 0.0
    assert benzene["heavy_atoms"] == 6
    assert benzene["heteroatoms"] == 0
    assert aspirin["ring_count"] == 1
    assert aspirin["aromatic_ring_count"] == 1
    # RDKit's strict definition counts the two aryl/ester single bonds, not the
    # ester methyl bond.
    assert aspirin["rotatable_bonds"] == 2
    assert aspirin["heavy_atoms"] == 13
    assert aspirin["heteroatoms"] == 4
    assert 20.0 < float(ethanol["tpsa"]) < 21.0
    assert -0.1 < float(ethanol["logp"]) < 0.1
    assert form.data.dtype == np.float32
    assert exported["n_molecules"] == 3


def test_descriptors_are_deterministic():
    pytest.importorskip("rdkit")
    step = RdkitDescriptorsStep()
    first, _ = _run(step, {"smiles": "CCO"})
    second, _ = _run(step, {"smiles": "CCO"})
    np.testing.assert_array_equal(first.data, second.data)


def test_descriptors_reject_bad_input():
    pytest.importorskip("rdkit")
    step = RdkitDescriptorsStep()
    with pytest.raises(StepError, match="at least one SMILES"):
        _run(step, {"smiles": "  \n# only comments\n"})
    with pytest.raises(StepError, match="cannot parse SMILES 'C1CC'"):
        _run(step, {"smiles": "C1CC broken"})


def test_morgan_fingerprint_matches_rdkit_reference():
    pytest.importorskip("rdkit")
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors

    step = RdkitMorganFingerprintStep()
    form, exported = _run(
        step,
        {"smiles": "CCO ethanol\nc1ccccc1 benzene", "radius": 2, "n_bits": 256},
    )
    assert form.dims == ["molecule", "bit"]
    assert form.data.shape == (2, 256)
    assert set(np.unique(form.data)).issubset({0.0, 1.0})
    for row, smiles in enumerate(["CCO", "c1ccccc1"]):
        reference = rdMolDescriptors.GetMorganFingerprintAsBitVect(
            Chem.MolFromSmiles(smiles), 2, nBits=256
        )
        expected = np.array([int(bit) for bit in reference.ToBitString()])
        np.testing.assert_array_equal(form.data[row].astype(int), expected)
    assert exported["n_bits"] == 256
    assert exported["radius"] == 2
    assert form.info["on_bits"] == [float(row.sum()) for row in form.data]


def test_morgan_fingerprint_validation():
    pytest.importorskip("rdkit")
    step = RdkitMorganFingerprintStep()
    with pytest.raises(StepError, match="radius must be between 1 and 6"):
        _run(step, {"smiles": "CCO", "radius": 9})
    with pytest.raises(StepError, match="n_bits must be between 64 and 16384"):
        _run(step, {"smiles": "CCO", "n_bits": 8})


def test_standardize_is_canonical_and_removes_salts():
    pytest.importorskip("rdkit")
    step = SmilesStandardizeStep()
    form, exported = _run(
        step,
        {
            "smiles": "C1=CC=CC=C1 benzene\nCC(=O)[O-].[Na+] acetate_salt",
            "keep_largest_fragment": True,
        },
    )
    assert form.dims == ["molecule", "statistic"]
    assert list(form.labels["molecule"]) == ["benzene", "acetate_salt"]
    assert form.info["canonical_smiles"] == [
        "c1ccccc1",
        "CC(=O)[O-]",
    ]
    assert form.info["changed"] == [True, True]
    assert form.data.shape == (2, 4)
    benzene = dict(zip(form.labels["statistic"], form.data[0]))
    assert benzene["n_atoms"] == 6
    assert benzene["n_heavy_atoms"] == 6
    assert benzene["n_fragments"] == 1
    assert benzene["n_rings"] == 1
    assert exported["statistics"] == list(form.labels["statistic"])
    assert exported["canonical_smiles"] == form.info["canonical_smiles"]


def test_standardize_can_keep_fragments_and_neutralize():
    pytest.importorskip("rdkit")
    step = SmilesStandardizeStep()

    kept, _ = _run(
        step,
        {
            "smiles": "CCO.[Na+] mixture",
            "keep_largest_fragment": False,
        },
    )
    assert kept.info["canonical_smiles"] == ["CCO.[Na+]"]
    assert kept.data[0][2] == 2  # n_fragments

    neutral, _ = _run(
        step,
        {"smiles": "[NH4+] ammonium", "neutralize": True},
    )
    assert neutral.info["canonical_smiles"] == ["N"]
    assert neutral.info["changed"] == [True]


def test_standardize_rejects_bad_smiles():
    pytest.importorskip("rdkit")
    step = SmilesStandardizeStep()
    with pytest.raises(StepError, match="cannot parse SMILES"):
        _run(step, {"smiles": "not a smiles"})
    with pytest.raises(StepError, match="smiles is required"):
        _run(step, {"smiles": "\n\n"})
