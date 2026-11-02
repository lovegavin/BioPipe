"""Tests for pairwise reaction enumeration."""

from __future__ import annotations

import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._rdkit_common import build_molecules
from src.task.step.steps.rdkit_reaction_pairwise_enumerate import (
    enumerate_pairs,
    reaction_from_smarts,
)

rdkit = pytest.importorskip("rdkit")

AMIDE = "[C:1](=[O:2])[OH:3].[N:4][H:5]>>[C:1](=[O:2])[N:4]"


def _params(**overrides):
    params = {
        "reactants_a": "CC(=O)O acid",
        "reactants_b": "CN methylamine",
        "reaction_smarts": AMIDE,
        "max_products": 100,
        "max_products_per_pair": 20,
        "dedupe": True,
        "output": "products",
    }
    params.update(overrides)
    return params


def test_reaction_from_smarts_requires_two_components():
    reaction = reaction_from_smarts(AMIDE)
    assert reaction.GetNumReactantTemplates() == 2
    with pytest.raises(StepError, match="reaction_smarts is required"):
        reaction_from_smarts("")
    with pytest.raises(StepError, match="two reactant templates"):
        reaction_from_smarts("[C:1]>>[C:1]")
    with pytest.raises(StepError, match="cannot parse reaction_smarts"):
        reaction_from_smarts("[C:1")


def test_enumerate_pairs_amide_coupling():
    reaction = reaction_from_smarts(AMIDE)
    products, stats = enumerate_pairs(
        reaction,
        build_molecules("CC(=O)O acid", "test"),
        build_molecules("CN methylamine", "test"),
    )
    assert len(products) == 1
    assert products[0]["smiles"] == "CC(=O)NC"
    assert products[0]["heavy_atoms"] == 5.0
    assert products[0]["molecular_weight"] == pytest.approx(73.09, abs=0.05)
    assert stats == {"n_pairs": 1, "truncated": False}


def test_enumerate_pairs_cross_product_and_dedupe():
    reaction = reaction_from_smarts(AMIDE)
    products, stats = enumerate_pairs(
        reaction,
        build_molecules("CC(=O)O acid\nCCC(=O)O propionic", "test"),
        build_molecules("CN methylamine\nCCN ethylamine", "test"),
    )
    assert stats["n_pairs"] == 4
    assert len(products) == 4
    names = {(item["reactant_a"], item["reactant_b"]) for item in products}
    assert names == {
        ("acid", "methylamine"),
        ("acid", "ethylamine"),
        ("propionic", "methylamine"),
        ("propionic", "ethylamine"),
    }

    duplicated, duplicated_stats = enumerate_pairs(
        reaction,
        build_molecules("CC(=O)O acid\nOC(=O)C acid2", "test"),
        build_molecules("CN amine", "test"),
    )
    assert duplicated_stats["n_pairs"] == 2
    assert len(duplicated) == 1


def test_enumerate_pairs_truncates():
    reaction = reaction_from_smarts(AMIDE)
    products, stats = enumerate_pairs(
        reaction,
        build_molecules("CC(=O)O acid", "test"),
        build_molecules("CN amine", "test"),
        max_products=1,
    )
    assert len(products) == 1
    assert stats["truncated"] is True


def test_run_writes_product_table(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = _params()
    run(ctx, [
        {
            "name": "rdkit_reaction_pairwise_enumerate",
            "inputs": [],
            "params": dict(ctx.step_params),
        }
    ])
    output = ctx["products"]
    assert list(output.dims) == ["product", "statistic"]
    assert output.data.shape == (1, 3)
    assert output.labels["product"]["acid+methylamine:1"] == 0
    assert output.data[0].tolist() == pytest.approx([5.0, 73.09, 1.0], abs=0.05)
    assert output.info["n_products"] == 1
    assert output.info["n_pairs"] == 1
    assert output.info["products"][0]["smiles"] == "CC(=O)NC"


def test_run_validation_errors(tmp_path):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = _params(reactants_a="")
    with pytest.raises(StepError, match="at least one SMILES"):
        run(ctx, [
            {
                "name": "rdkit_reaction_pairwise_enumerate",
                "inputs": [],
                "params": dict(ctx.step_params),
            }
        ])

    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = _params(reactants_b="C1CC bad")
    with pytest.raises(StepError, match="cannot parse SMILES"):
        run(ctx, [
            {
                "name": "rdkit_reaction_pairwise_enumerate",
                "inputs": [],
                "params": dict(ctx.step_params),
            }
        ])

    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = _params(max_products=10000)
    with pytest.raises((StepError, ValueError), match="max_products"):
        run(ctx, [
            {
                "name": "rdkit_reaction_pairwise_enumerate",
                "inputs": [],
                "params": dict(ctx.step_params),
            }
        ])
