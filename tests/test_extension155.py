"""Tests for the RDKit fragment profile operator."""

from __future__ import annotations

import numpy as np
import pytest
from rdkit import Chem
from rdkit.Chem import BRICS

from src.core.errors import StepError
from src.task.step.steps.rdkit_fragment_profile import (
    RdkitFragmentProfileStep,
    brics_fragments,
    clean_fragment,
    recap_fragments,
)


class Ctx(dict):
    def __init__(self, params: dict) -> None:
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(step, params):
    ctx = Ctx(params)
    step.run(ctx, [])
    return ctx[ctx.step_params["output"]], step.export(ctx)


def test_clean_fragment_removes_dummies():
    assert clean_fragment("[1*]C(=O)O") == "O=C(O)*" or clean_fragment("[1*]C(=O)O") == "O=CO"
    cleaned = clean_fragment("[3*]c1ccccc1")
    assert "*" not in cleaned
    assert Chem.MolFromSmiles(cleaned) is not None


def test_brics_fragments_match_rdkit():
    molecule = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
    assert molecule is not None
    expected = {clean_fragment(item) for item in BRICS.BRICSDecompose(molecule, minFragmentSize=2)}
    assert set(brics_fragments(molecule)) == expected
    assert brics_fragments(molecule) == sorted(expected)


def test_recap_fragments_are_valid_smiles():
    molecule = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
    assert molecule is not None
    fragments = recap_fragments(molecule)
    assert fragments
    for fragment in fragments:
        assert Chem.MolFromSmiles(fragment) is not None, fragment


def test_fragment_matrix_is_presence_per_molecule():
    smiles = "CCO ethanol\nc1ccccc1 benzene\nCC(=O)Oc1ccccc1C(=O)O aspirin"
    out, export = _run(RdkitFragmentProfileStep(), {"smiles": smiles, "method": "brics"})
    assert list(out.dims) == ["molecule", "fragment"]
    assert out.data.shape[0] == 3
    assert out.data.shape[1] == len(out.info["fragments"])
    assert out.info["method"] == "brics"
    assert out.info["n_molecules"] == 3
    assert export["n_molecules"] == 3
    for row in out.data:
        assert set(np.unique(row)) <= {0.0, 1.0}
    for name, fragments in out.info["molecule_fragments"].items():
        row = out.labels["molecule"][name]
        present = {column for column, value in enumerate(out.data[row]) if value > 0}
        expected = {out.labels["fragment"][fragment] for fragment in fragments}
        assert present == expected


def test_fragment_profile_recap_method():
    out, _ = _run(
        RdkitFragmentProfileStep(),
        {"smiles": "CC(=O)Oc1ccccc1C(=O)O aspirin", "method": "recap"},
    )
    assert out.info["method"] == "recap"
    assert out.data.shape[0] == 1
    assert out.data.sum() == len(out.info["molecule_fragments"]["aspirin"])


def test_fragment_profile_parameter_errors():
    with pytest.raises(StepError, match="method must be 'brics' or 'recap'"):
        _run(RdkitFragmentProfileStep(), {"smiles": "CCO", "method": "moses"})
    with pytest.raises(StepError, match="must differ"):
        _run(
            RdkitFragmentProfileStep(),
            {"smiles": "CCO", "molecule_dim": "x", "fragment_dim": "x"},
        )
    with pytest.raises(StepError, match="must contain at least one SMILES line"):
        _run(RdkitFragmentProfileStep(), {"smiles": "   "})
    with pytest.raises(StepError, match="cannot parse SMILES"):
        _run(RdkitFragmentProfileStep(), {"smiles": "notasmiles"})
