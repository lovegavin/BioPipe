"""Tests for conformer clustering."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import StepError
from src.task.step.steps.rdkit_conformer_cluster import (
    RdkitConformerClusterStep,
    _embed,
    cluster_conformers,
    conformer_rmsds,
)


class Ctx(dict):
    def __init__(self, params: dict):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _condensed_to_square(condensed, count: int) -> np.ndarray:
    square = np.zeros((count, count), dtype=float)
    index = 0
    for second in range(1, count):
        for first in range(second):
            square[second, first] = square[first, second] = float(condensed[index])
            index += 1
    return square


def test_conformer_rmsds_are_symmetric() -> None:
    from rdkit import Chem

    molecule = Chem.AddHs(Chem.MolFromSmiles("CCCCCC"))
    embedded, conf_ids = _embed(molecule, "MMFF94", 3, 200, True, 7)
    distances = conformer_rmsds(embedded, conf_ids)
    assert distances.shape == (3, 3)
    assert np.allclose(np.diag(distances), 0.0)
    assert np.allclose(distances, distances.T)
    assert np.all(distances >= 0.0)


def test_cluster_conformers_hand_matrix() -> None:
    distances = np.array(
        [[0.0, 0.3, 2.0], [0.3, 0.0, 2.1], [2.0, 2.1, 0.0]], dtype=float
    )
    assert cluster_conformers(distances, 0.5) == [[0, 1], [2]]
    assert cluster_conformers(distances, 5.0) == [[0, 1, 2]]
    assert cluster_conformers(np.zeros((1, 1)), 0.5) == [[0]]


def test_step_writes_membership_matrix() -> None:
    step = RdkitConformerClusterStep()
    ctx = Ctx({"smiles": "CCCCCC hexane\nc1ccccc1 benzene", "num_conformers": 6, "seed": 11})
    step.run(ctx, [])
    out = ctx["out"]
    assert out.dims == ["molecule", "cluster"]
    assert out.data.shape[0] == 2
    assert out.data.shape[1] == out.info["max_clusters"]
    conformer_counts = [entry["n_conformers"] for entry in out.info["molecules"]]
    assert np.allclose(out.data.sum(axis=1), conformer_counts)
    assert out.labels["molecule"] == {"hexane": 0, "benzene": 1}
    assert out.info["n_molecules"] == 2
    assert out.info["cluster_cutoff"] == pytest.approx(0.5)
    assert out.info["force_field"] == "MMFF94"
    for entry in out.info["molecules"]:
        assert sum(len(members) for members in entry["clusters"]) == entry["n_conformers"]
        assert len(entry["clusters"]) == len(out.data[out.labels["molecule"][entry["name"]]][out.data[out.labels["molecule"][entry["name"]]] > 0])
    export = step.export(ctx)
    assert export["n_molecules"] == 2
    assert export["total_conformers"] >= 2


def test_rmsd_matches_rdkit_conformer_matrix() -> None:
    from rdkit import Chem
    from rdkit.Chem import AllChem

    molecule = Chem.AddHs(Chem.MolFromSmiles("CCOCC"))
    embedded, conf_ids = _embed(molecule, "MMFF94", 6, 200, True, 3)
    plain = Chem.RemoveHs(embedded)
    count = plain.GetNumConformers()
    distances = conformer_rmsds(embedded, conf_ids)
    matrix = AllChem.GetConformerRMSMatrix(plain, prealigned=False)
    square = _condensed_to_square(matrix, count)
    assert distances.shape == square.shape


def test_deterministic_seed() -> None:
    step = RdkitConformerClusterStep()
    first = Ctx({"smiles": "CCOCC", "num_conformers": 5, "seed": 5})
    second = Ctx({"smiles": "CCOCC", "num_conformers": 5, "seed": 5})
    step.run(first, [])
    RdkitConformerClusterStep().run(second, [])
    assert np.array_equal(first["out"].data, second["out"].data)
    assert first["out"].info["molecules"] == second["out"].info["molecules"]


def test_parameter_errors() -> None:
    with pytest.raises(StepError, match="smiles is required"):
        RdkitConformerClusterStep().run(Ctx({"smiles": "  "}), [])
    with pytest.raises(StepError, match="num_conformers"):
        RdkitConformerClusterStep().run(Ctx({"smiles": "CCO", "num_conformers": 1}), [])
    with pytest.raises(StepError, match="num_conformers"):
        RdkitConformerClusterStep().run(Ctx({"smiles": "CCO", "num_conformers": 51}), [])
    with pytest.raises(StepError, match="cluster_cutoff"):
        RdkitConformerClusterStep().run(Ctx({"smiles": "CCO", "cluster_cutoff": 0.0}), [])
    with pytest.raises(StepError, match="force_field"):
        RdkitConformerClusterStep().run(Ctx({"smiles": "CCO", "force_field": "X"}), [])
    with pytest.raises(StepError, match="must differ"):
        RdkitConformerClusterStep().run(Ctx({"smiles": "CCO", "molecule_dim": "cluster"}), [])
    with pytest.raises(StepError, match="cannot parse SMILES"):
        RdkitConformerClusterStep().run(Ctx({"smiles": "notasmiles"}), [])
