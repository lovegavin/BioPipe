"""Extension tests for the RDKit synthetic accessibility operator."""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

rdkit = pytest.importorskip("rdkit")
from rdkit import Chem  # noqa: E402

from src.core.errors import StepError
from src.task.step.steps.rdkit_sa_score import sa_class, sa_score

from rdkit import RDConfig  # noqa: E402

sys.path.append(os.path.join(RDConfig.RDContribDir, "SA_Score"))
import sascorer  # noqa: E402

STEP = pytest.importorskip("src.task.step.steps.rdkit_sa_score").RdkitSaScoreStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(params):
    step = STEP()
    ctx = Ctx(params)
    step.run(ctx, [])
    return ctx["out"], step.export(ctx)


def test_scores_match_official_scorer():
    smiles = ["CCO", "c1ccccc1", "CC(=O)Oc1ccccc1C(=O)O"]
    out, export = _run({"smiles": "\n".join(smiles)})
    assert out.data.shape == (3, 1)
    expected = [sascorer.calculateScore(Chem.MolFromSmiles(value)) for value in smiles]
    np.testing.assert_allclose(out.data.ravel(), expected, rtol=1e-6, atol=1e-6)
    assert list(out.labels["molecule"]) == ["mol1", "mol2", "mol3"]
    assert list(out.labels["statistic"]) == ["sa_score"]
    assert out.info["n_molecules"] == 3
    assert export["mean_score"] == pytest.approx(float(np.mean(expected)), rel=1e-5)


def test_class_buckets():
    assert sa_class(1.0) == "easy"
    assert sa_class(4.99) == "moderate"
    assert sa_class(5.0) == "hard"
    assert sa_class(9.0) == "very hard"
    out, _ = _run({"smiles": "CCO ethanol"})
    assert out.info["classes"] == ["easy"]
    assert list(out.labels["molecule"]) == ["ethanol"]


def test_named_lines_and_blank_lines():
    out, _ = _run({"smiles": "\nCCO ethanol\n\nc1ccccc1 ring\n"})
    assert out.data.shape == (2, 1)
    assert list(out.labels["molecule"]) == ["ethanol", "ring"]


def test_rejects_empty_smiles():
    with pytest.raises(StepError, match="at least one SMILES line"):
        _run({"smiles": "  \n "})


def test_rejects_unparsable_smiles():
    with pytest.raises(StepError, match="cannot parse"):
        _run({"smiles": "notasmiles"})


def test_rejects_molecule_without_heavy_atoms():
    with pytest.raises(StepError, match="without heavy atoms"):
        _run({"smiles": "[H][H]"})


def test_custom_molecule_dim():
    out, _ = _run({"smiles": "CCO", "molecule_dim": "compound"})
    assert out.dims == ["compound", "statistic"]
    assert "compound" in out.labels


def test_helper_rejects_empty_molecule():
    with pytest.raises(StepError, match="without heavy atoms"):
        sa_score(Chem.MolFromSmiles("[H]"))
