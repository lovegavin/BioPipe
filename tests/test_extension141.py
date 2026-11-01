"""Tests for the RDKit SMARTS match matrix operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps.rdkit_smarts_matches import (
    RdkitSmartsMatchesStep,
    count_matches,
    parse_patterns,
)


class _Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "smarts_matches", **params}
        self.metadata = {}


def _run(params):
    ctx = _Ctx(params)
    step = RdkitSmartsMatchesStep()
    step.run(ctx, [])
    return ctx["smarts_matches"], step.export(ctx)


def test_parse_patterns() -> None:
    assert parse_patterns("c1ccccc1\n[OH];[CX4]") == ["c1ccccc1", "[OH]", "[CX4]"]
    with pytest.raises(StepError, match="smarts is required"):
        parse_patterns("")
    with pytest.raises(StepError, match="cannot parse SMARTS"):
        parse_patterns("notasmarts")


def test_count_matches_matches_rdkit() -> None:
    from rdkit import Chem

    molecule = Chem.MolFromSmiles("c1ccccc1C")
    query = Chem.MolFromSmarts("[cH]")
    assert count_matches(molecule, query, True) == len(
        molecule.GetSubstructMatches(query, uniquify=True)
    )
    assert count_matches(molecule, query, False) >= count_matches(molecule, query, True)


def test_matrix_is_consistent_with_rdkit() -> None:
    from rdkit import Chem

    smiles = "c1ccccc1 benzene\nCc1ccccc1 toluene\nCCO ethanol"
    patterns = "c1ccccc1\n[OH]\n[CX4]"
    form, exported = _run({"smiles": smiles, "smarts": patterns})
    assert form.data.shape == (3, 3)
    assert list(form.dims) == ["molecule", "pattern"]
    assert list(form.labels["pattern"]) == ["c1ccccc1", "[OH]", "[CX4]"]
    expected = np.zeros((3, 3))
    for row, text in enumerate(("c1ccccc1", "Cc1ccccc1", "CCO")):
        molecule = Chem.MolFromSmiles(text)
        for column, pattern in enumerate(patterns.splitlines()):
            query = Chem.MolFromSmarts(pattern)
            expected[row, column] = len(molecule.GetSubstructMatches(query, uniquify=True))
    np.testing.assert_allclose(form.data, expected, atol=0)
    assert form.info["patterns"] == patterns.splitlines()
    assert exported["total_matches"] == int(expected.sum())
    assert exported["n_patterns"] == 3


def test_unique_false_counts_more_symmetry() -> None:
    form_unique, _ = _run({"smiles": "c1ccccc1", "smarts": "c1ccccc1", "unique": True})
    form_all, _ = _run({"smiles": "c1ccccc1", "smarts": "c1ccccc1", "unique": False})
    assert form_unique.data[0, 0] == 1
    assert form_all.data[0, 0] == 12  # six atom starts x two directions


def test_custom_dims() -> None:
    form, _ = _run({"smiles": "CCO", "smarts": "[OH]", "molecule_dim": "compound", "pattern_dim": "smarts"})
    assert list(form.dims) == ["compound", "smarts"]


def test_dimension_collision_is_rejected() -> None:
    with pytest.raises(StepError, match="must differ"):
        _run({"smiles": "CCO", "smarts": "[OH]", "molecule_dim": "x", "pattern_dim": "x"})


def test_missing_patterns_are_rejected() -> None:
    with pytest.raises(StepError, match="smarts is required"):
        _run({"smiles": "CCO"})
