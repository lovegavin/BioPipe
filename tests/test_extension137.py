"""Tests for the RDKit tautomer enumeration operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps.rdkit_tautomer import (
    _STATISTICS,
    RdkitTautomerStep,
    tautomer_profile,
)


class Ctx(dict):
    def __init__(self, params):
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(smiles, **params):
    step = RdkitTautomerStep()
    ctx = Ctx({"smiles": smiles, **params})
    step.run(ctx, [])
    return ctx["out"], step.export(ctx)


def test_pyridone_tautomers():
    profile = tautomer_profile("Oc1ccccn1")
    assert profile["input_smiles"] == "Oc1ccccn1"
    assert profile["canonical_smiles"] == "O=c1cccc[nH]1"
    assert profile["canonical_changed"] == 1.0
    assert profile["n_tautomers"] == 3.0
    assert profile["canonical_heavy_atoms"] == 7.0
    assert profile["canonical_hbd"] == 1.0
    assert profile["canonical_hba"] == 1.0
    assert profile["n_aromatic_rings"] == 1.0
    assert "Oc1ccccn1" in profile["tautomer_smiles"]
    assert "O=c1cccc[nH]1" in profile["tautomer_smiles"]
    assert len(profile["tautomer_smiles"]) == 3


def test_benzene_has_one_tautomer():
    profile = tautomer_profile("c1ccccc1")
    assert profile["n_tautomers"] == 1.0
    assert profile["canonical_changed"] == 0.0
    assert profile["canonical_smiles"] == "c1ccccc1"


def test_step_output_rows():
    out, export = _run("Oc1ccccn1\nCC(=O)O")
    assert list(out.dims) == ["molecule", "statistic"]
    assert [label for label, _ in sorted(out.labels["molecule"].items(), key=lambda item: item[1])] == [
        "mol1",
        "mol2",
    ]
    assert [label for label, _ in sorted(out.labels["statistic"].items(), key=lambda item: item[1])] == list(
        _STATISTICS
    )
    np.testing.assert_allclose(out.data[0], np.array([3, 1, 7, 1, 1, 1], np.float32))
    assert export["n_molecules"] == 2
    assert out.info["canonical_smiles"] == ["O=c1cccc[nH]1", "CC(=O)O"]
    assert sorted(out.info["tautomer_smiles"][1]) == ["C=C(O)O", "CC(=O)O"]


def test_rdkit_oracle():
    Chem = pytest.importorskip("rdkit.Chem")
    standardize = pytest.importorskip("rdkit.Chem.MolStandardize.rdMolStandardize")

    for smiles in ("Oc1ccccn1", "CC(=O)O", "c1ccccc1", "CC(N)=O"):
        enumerator = standardize.TautomerEnumerator()
        enumerated = enumerator.Enumerate(Chem.MolFromSmiles(smiles))
        oracle = sorted({Chem.MolToSmiles(molecule) for molecule in enumerated} | {
            Chem.MolToSmiles(enumerator.Canonicalize(Chem.MolFromSmiles(smiles)))
        })
        profile = tautomer_profile(smiles)
        assert profile["tautomer_smiles"] == oracle
        assert profile["n_tautomers"] == float(len(oracle))


def test_parameter_errors():
    with pytest.raises(StepError, match="smiles"):
        _run("")
    with pytest.raises(StepError, match="cannot parse"):
        _run("notasmiles")
    with pytest.raises(StepError, match="max_tautomers"):
        _run("CCO", max_tautomers=0)
    with pytest.raises(StepError, match="max_tautomers"):
        _run("CCO", max_tautomers=2000)


def test_heavy_atom_guard():
    with pytest.raises(StepError, match="no heavy atoms"):
        tautomer_profile("")
