"""Tests for the v1.30.0 rdkit_mcs_cluster operator."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("rdkit")

from src.core.errors import StepError
from src.task.step.steps.rdkit_mcs_cluster import (
    RdkitMcsClusterStep,
    cluster_matrix,
    mcs_similarity,
)

SMILES = "c1ccccc1 benzene\nCc1ccccc1 toluene\nCCO ethanol\nC1CCCCC1 cyclohexane"


def _run(step, params):
    class Ctx(dict):
        def __init__(self, params):
            self.step_params = {"output": "out", **params}
            self.metadata = {}

    ctx = Ctx(params)
    step.run(ctx, [])
    return ctx[params.get("output", "out")]


def _molecules():
    from rdkit import Chem

    return [Chem.MolFromSmiles(line.split()[0]) for line in SMILES.splitlines()]


def test_pairwise_matches_rdkit() -> None:
    from rdkit.Chem import rdFMCS

    molecules = _molecules()
    matrix = mcs_similarity(molecules)
    assert matrix.shape == (4, 4)
    np.testing.assert_allclose(np.diag(matrix), 1.0)
    np.testing.assert_allclose(matrix, matrix.T)
    for left in range(4):
        for right in range(left + 1, 4):
            result = rdFMCS.FindMCS([molecules[left], molecules[right]])
            smaller = min(
                molecules[left].GetNumHeavyAtoms(),
                molecules[right].GetNumHeavyAtoms(),
            )
            expected = result.numAtoms / smaller
            assert matrix[left, right] == pytest.approx(expected, abs=1e-9)


def test_cluster_matrix_single_linkage() -> None:
    similarity = np.array(
        [
            [1.0, 0.9, 0.2, 0.0],
            [0.9, 1.0, 0.3, 0.0],
            [0.2, 0.3, 1.0, 0.75],
            [0.0, 0.0, 0.75, 1.0],
        ]
    )
    membership, clusters = cluster_matrix(similarity, 0.4)
    assert clusters == [[0, 1], [2, 3]]
    assert membership.shape == (4, 2)
    np.testing.assert_allclose(membership.sum(axis=1), 1.0)


def test_step_output() -> None:
    step = RdkitMcsClusterStep()
    form = _run(step, {"smiles": SMILES, "distance_cutoff": 0.4})
    assert list(form.dims) == ["molecule", "cluster"]
    assert list(form.labels["molecule"]) == ["benzene", "toluene", "ethanol", "cyclohexane"]
    assert form.info["n_molecules"] == 4
    assert form.info["n_clusters"] == len(clusters_of(form))
    sizes = sorted(form.info["cluster_sizes"], reverse=True)
    assert sum(sizes) == 4
    assert form.info["metric"] == "mcs_over_smaller_heavy_atoms"


def clusters_of(form):
    membership = np.asarray(form.data)
    return {
        tuple(int(index) for index in np.flatnonzero(membership[:, column]))
        for column in range(membership.shape[1])
    }


def test_membership_matches_matrix() -> None:
    step = RdkitMcsClusterStep()
    form = _run(step, {"smiles": SMILES, "distance_cutoff": 0.6})
    report = form.info["similarity_matrix"]
    similarity = np.asarray(report, dtype=np.float64)
    membership, clusters = cluster_matrix(similarity, 0.6)
    expected = {
        tuple(index for index in range(4) if membership[index, position] > 0)
        for position in range(len(clusters))
    }
    assert clusters_of(form) == expected


def test_errors() -> None:
    step = RdkitMcsClusterStep()
    with pytest.raises(StepError, match="at least twice|at least two molecules"):
        _run(step, {"smiles": "CCO ethanol"})
    with pytest.raises(StepError, match="not parse"):
        _run(step, {"smiles": "notasmiles x\nCCO y"})
    with pytest.raises(StepError, match="between 0 and 1"):
        _run(step, {"smiles": SMILES, "distance_cutoff": 1.5})
    with pytest.raises(StepError, match="must differ"):
        _run(step, {"smiles": SMILES, "molecule_dim": "m", "cluster_dim": "m"})
    with pytest.raises(StepError, match="at least one SMILES"):
        _run(step, {"smiles": "  \n# nothing\n"})
