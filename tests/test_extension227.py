"""Tests for the SMARTS functional-group count operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps.rdkit_functional_group_counts import (
    GROUP_NAMES,
    GROUPS,
    RdkitFunctionalGroupCountsStep,
    group_counts,
)

pytest.importorskip("rdkit")

from rdkit import Chem  # noqa: E402


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "groups", **params}
        self.metadata = {}


def _row(text: str, params: dict | None = None) -> dict[str, float]:
    ctx = Ctx({"smiles": text, **(params or {})})
    step = RdkitFunctionalGroupCountsStep()
    step.run(ctx, [])
    out = ctx["groups"]
    return {name: float(out.data[0, index]) for index, name in enumerate(GROUP_NAMES)}


def test_hand_computed_counts() -> None:
    acetic_acid = _row("CC(=O)O acetic")
    assert acetic_acid["carboxyl"] == 1
    assert acetic_acid["hydroxyl"] == 1
    assert acetic_acid["ester"] == 0
    assert acetic_acid["aromatic_ring"] == 0
    assert acetic_acid["halogen"] == 0

    benzene = _row("c1ccccc1 benzene")
    assert benzene["aromatic_ring"] == 1
    assert benzene["hydroxyl"] == 0

    paracetamol = _row("CC(=O)Nc1ccc(O)cc1 paracetamol")
    assert paracetamol["amide"] == 1
    assert paracetamol["hydroxyl"] == 1
    assert paracetamol["aromatic_ring"] == 1
    assert paracetamol["ketone"] == 0

    nitrile = _row("CC#N acetonitrile")
    assert nitrile["nitrile"] == 1
    assert nitrile["primary_amine"] == 0

    chloroacetic = _row("OC(=O)CCl chloroacetic")
    assert chloroacetic["halogen"] == 1
    assert chloroacetic["carboxyl"] == 1


def test_multiple_molecules_and_labels() -> None:
    ctx = Ctx({"smiles": "CCO ethanol\nCC(=O)O acetic"})
    step = RdkitFunctionalGroupCountsStep()
    step.run(ctx, [])
    out = ctx["groups"]
    assert out.data.shape == (2, len(GROUPS))
    assert list(out.labels["molecule"]) == ["ethanol", "acetic"]
    assert list(out.labels["group"]) == list(GROUP_NAMES)
    assert out.info["n_molecules"] == 2
    assert out.info["smarts"]["carboxyl"] == "[CX3](=O)[OX2H1]"
    assert step.export(ctx)["n_groups"] == len(GROUPS)


def test_unique_match_per_group() -> None:
    # RDKit's default uniquify=True collapses the six rotationally equivalent
    # benzene matches into one.
    molecule = Chem.MolFromSmiles("c1ccccc1")
    patterns = [(name, Chem.MolFromSmarts(smarts)) for name, smarts in GROUPS]
    counts = group_counts(molecule, patterns)
    assert counts[GROUP_NAMES.index("aromatic_ring")] == 1
    assert sum(counts) == 1


def test_errors() -> None:
    with pytest.raises(StepError, match="at least one SMILES"):
        _row("")
    with pytest.raises(StepError, match="cannot parse SMILES"):
        _row("C1CC")


def test_dtype() -> None:
    ctx = Ctx({"smiles": "CCO ethanol"})
    RdkitFunctionalGroupCountsStep().run(ctx, [])
    assert ctx["groups"].data.dtype == np.float32
