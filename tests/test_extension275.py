"""rdkit_reaction_pairwise_enumerate: two-component reaction enumeration."""

import numpy as np
import pytest

pytest.importorskip("rdkit")

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.rdkit_reaction_pairwise_enumerate import (
    enumerate_pairs,
    reaction_from_smarts,
)


EPOXIDE = "[C:1]1[O:2][C:3]1.[N:4]>>[C:1][O:2][C:3][N:4]"


def _library(text):
    from src.task.step.steps._rdkit_common import build_molecules

    return build_molecules(text, "rdkit_reaction_pairwise_enumerate")


def test_reaction_from_smarts_requires_two_components():
    reaction = reaction_from_smarts(EPOXIDE)
    assert reaction is not None
    with pytest.raises(StepError, match="must declare two reactant templates"):
        reaction_from_smarts("[C:1]>>[C:1]")


def test_enumerate_pairs_epoxide_opening():
    products, stats = enumerate_pairs(reaction_from_smarts(EPOXIDE), _library("C1CO1 oxirane"), _library("CN methylamine"))
    assert len(products) == 1
    assert products[0]["smiles"] == "CNCOC"
    assert products[0]["heavy_atoms"] == 5
    assert products[0]["molecular_weight"] == pytest.approx(75.111, rel=1e-3)
    assert stats == {"n_pairs": 1, "truncated": False}


def test_enumerate_pairs_cross_product_and_dedupe():
    products, stats = enumerate_pairs(
        reaction_from_smarts(EPOXIDE),
        _library("C1CO1 a\nC1COC1 b"),
        _library("CN m\nCCN e"),
    )
    assert stats["n_pairs"] == 4
    assert len(products) >= 2
    with pytest.raises(StepError, match="cannot parse SMILES"):
        _library("not-a-smiles bad")


def test_enumerate_pairs_truncates():
    products, stats = enumerate_pairs(
        reaction_from_smarts(EPOXIDE),
        _library("C1CO1 a\nC1COC1 b"),
        _library("CN m\nCCN e"),
        max_products=1,
    )
    assert len(products) == 1
    assert stats["truncated"] is True


def test_run_writes_product_table():
    ctx = Context("/tmp/operon_test_275", {"params": {}})
    ctx.step_params = {
        "output": "products",
        "reactants_a": "C1CO1 oxirane",
        "reactants_b": "CN methylamine",
        "reaction_smarts": EPOXIDE,
    }
    run(ctx, [{"name": "rdkit_reaction_pairwise_enumerate", "params": {"output": "products", "reactants_a": "C1CO1 oxirane", "reactants_b": "CN methylamine", "reaction_smarts": EPOXIDE}}])
    result = ctx["products"]
    assert result.dims == ["product", "statistic"]
    assert result.data.shape[0] == 1
