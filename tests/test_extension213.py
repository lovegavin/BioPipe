"""Tests for the Murcko scaffold fingerprint operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps.rdkit_murcko_fingerprint import RdkitMurckoFingerprintStep, scaffold_fingerprint

pytest.importorskip("rdkit")


class Ctx(dict):
    def __init__(self, params: dict):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(params: dict):
    ctx = Ctx(params)
    step = RdkitMurckoFingerprintStep()
    step.run(ctx, [])
    return ctx[ctx.step_params.get("output", "out")], step.export(ctx)


def _oracle(smiles: str, radius: int, n_bits: int) -> np.ndarray:
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    from rdkit.Chem.Scaffolds import MurckoScaffold

    molecule = Chem.MolFromSmiles(smiles)
    scaffold = MurckoScaffold.GetScaffoldForMol(molecule)
    if scaffold.GetNumHeavyAtoms() == 0:
        return np.zeros(n_bits, dtype=np.float32)
    fingerprint = rdMolDescriptors.GetMorganFingerprintAsBitVect(scaffold, radius, nBits=n_bits)
    bits = np.zeros(n_bits, dtype=np.float32)
    for index in fingerprint.GetOnBits():
        bits[int(index)] = 1.0
    return bits


def test_scaffold_fingerprint_matches_rdkit() -> None:
    for smiles in ("c1ccccc1", "Cc1ccccc1", "CCCCCC", "Oc1ccccc1"):
        produced = scaffold_fingerprint(smiles, radius=2, n_bits=128)
        np.testing.assert_allclose(produced, _oracle(smiles, 2, 128), rtol=0, atol=0)


def test_acyclic_scaffold_is_all_zero() -> None:
    produced = scaffold_fingerprint("CCCCCC", radius=2, n_bits=64)
    assert produced.sum() == 0.0
    benzene = scaffold_fingerprint("c1ccccc1", radius=2, n_bits=64)
    toluene = scaffold_fingerprint("Cc1ccccc1", radius=2, n_bits=64)
    np.testing.assert_allclose(benzene, toluene)


def test_step_output_and_labels() -> None:
    out, export = _run({"smiles": "c1ccccc1 benzene\nCCCCCC hexane", "n_bits": 64, "radius": 1})
    assert out.data.shape == (2, 64)
    assert out.dims == ["molecule", "bit"]
    assert out.labels["molecule"] == {"benzene": 0, "hexane": 1}
    assert out.labels["bit"]["0"] == 0
    assert out.info["n_bits"] == 64
    assert out.info["on_bits"][1] == 0
    assert export["n_molecules"] == 2


def test_parameter_errors() -> None:
    for params, match in (
        ({"smiles": ""}, "smiles is required"),
        ({"smiles": "c1ccccc1", "radius": 9}, "radius must be between"),
        ({"smiles": "c1ccccc1", "n_bits": 8}, "n_bits must be between"),
        ({"smiles": "c1ccccc1", "bit_dim": "molecule"}, "must differ"),
        ({"smiles": "c1ccccc1", "radius": "two"}, "radius must be an integer"),
    ):
        with pytest.raises(StepError, match=match):
            _run(params)
    with pytest.raises(StepError, match="cannot parse SMILES"):
        _run({"smiles": "notasmiles"})
