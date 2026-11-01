"""Tests for the RDKit random-SMILES augmentation operator."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("rdkit")

from rdkit import Chem

from src.core.errors import StepError
from src.task.step.steps.rdkit_smiles_augment import (
    RdkitSmilesAugmentStep,
    augment_row,
    random_smiles,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(params):
    step = RdkitSmilesAugmentStep()
    ctx = Ctx(params)
    step.run(ctx, [])
    return step, ctx


def test_random_smiles_reproducible() -> None:
    molecule = Chem.MolFromSmiles("CCO")
    first = random_smiles(molecule, 6, 7)
    second = random_smiles(molecule, 6, 7)
    assert first == second
    assert len(first) == 6
    for text in first:
        assert Chem.MolToSmiles(Chem.MolFromSmiles(text)) == "CCO"


def test_augment_row_counts_unique() -> None:
    molecule = Chem.MolFromSmiles("c1ccccc1")
    variants, row = augment_row(molecule, 4, 11)
    assert len(variants) == 4
    assert row[0] == 4
    assert 1 <= row[1] <= 4
    assert row[2] > 0
    assert row[3] >= row[2]


def test_step_output() -> None:
    step, ctx = _run({"smiles": "CCO ethanol\nc1ccccc1 benzene", "n_variants": 5, "seed": 3})
    out = ctx["out"]
    assert list(out.dims) == ["molecule", "statistic"]
    assert out.data.shape == (2, 4)
    assert list(out.labels["molecule"]) == ["ethanol", "benzene"]
    assert list(out.labels["statistic"]) == [
        "n_variants",
        "n_unique",
        "mean_length",
        "max_length",
    ]
    assert out.info["seed"] == 3
    assert len(out.info["variants"]) == 2
    assert all(len(value) == 5 for value in out.info["variants"])
    exported = step.export(ctx)
    assert exported["n_molecules"] == 2
    assert exported["variant_counts"] == [5, 5]


@pytest.mark.parametrize("count", [0, 201])
def test_variant_count_bounds(count: int) -> None:
    with pytest.raises(StepError, match="n_variants must be between"):
        _run({"smiles": "CCO", "n_variants": count})


def test_negative_seed() -> None:
    with pytest.raises(StepError, match="seed must not be negative"):
        _run({"smiles": "CCO", "seed": -1})


def test_empty_smiles() -> None:
    with pytest.raises(StepError, match="smiles"):
        _run({"smiles": ""})


def test_invalid_smiles() -> None:
    with pytest.raises(StepError, match="cannot parse"):
        _run({"smiles": "notasmiles"})
