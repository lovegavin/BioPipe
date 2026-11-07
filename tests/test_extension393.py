"""Numerical and contract tests for phylogenetic comparative operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps._tree_build_common import TreeNode, build_tree_form
from src.task.step.steps.phylo_ancestral import PhyloAncestralStep
from src.task.step.steps.phylo_contrasts import PhyloContrastsStep
from src.task.step.steps.phylo_lambda import PhyloLambdaStep


class Ctx:
    def __init__(self, **params):
        self.step_params = params
        self.outputs = {}

    def __setitem__(self, key, value):
        self.outputs[key] = value

    def __getitem__(self, key):
        return self.outputs[key]


def leaf(name, length):
    node = TreeNode(name)
    node.length = length
    return node


def join(name, children):
    node = TreeNode(name)
    node.length = np.nan
    for child, length in children:
        child.parent = node
        child.length = length
        node.children.append(child)
    return node


def balanced_tree(values):
    a, b, c, d = leaf("A", 1.0), leaf("B", 1.0), leaf("C", 1.0), leaf("D", 1.0)
    ab = join("AB", [(a, 1.0), (b, 1.0)])
    cd = join("CD", [(c, 1.0), (d, 1.0)])
    root = join("R", [(ab, 1.0), (cd, 1.0)])
    return build_tree_form(root, "node", "field", "tree"), ["A", "B", "C", "D"], values


def trait_form(names, values):
    data = np.asarray(values, dtype=np.float64).reshape(-1, 1)
    return Form(
        data,
        dims=["sample", "statistic"],
        labels={"sample": {name: index for index, name in enumerate(names)},
                "statistic": {"gc": 0}},
        info={},
    )


def run_step(step, params, tree_form, trait):
    step.name = step.definition["id"]
    ctx = Ctx(**params)
    step.run(ctx, [tree_form, trait])
    return ctx, ctx.outputs[params.get("output", "out")]


def test_contrasts_two_tips():
    a, b = leaf("A", 1.0), leaf("B", 1.0)
    root = join("R", [(a, 1.0), (b, 1.0)])
    tree = build_tree_form(root, "node", "field", "tree")
    step = PhyloContrastsStep()
    ctx, out = run_step(step, {"output": "contrasts"}, tree, trait_form(["A", "B"], [0.0, 2.0]))
    assert out.data.shape == (1, 2)
    assert abs(float(out.data[0, 0]) + np.sqrt(2.0)) < 1e-9
    assert abs(float(out.data[0, 1]) - 2.0) < 1e-9


def test_contrasts_reject_polytomy():
    a, b, c = leaf("A", 1.0), leaf("B", 1.0), leaf("C", 1.0)
    root = join("R", [(a, 1.0), (b, 1.0), (c, 1.0)])
    tree = build_tree_form(root, "node", "field", "tree")
    step = PhyloContrastsStep()
    with pytest.raises(StepError, match="binary"):
        run_step(step, {"output": "contrasts"}, tree, trait_form(["A", "B", "C"], [0.0, 1.0, 2.0]))


def test_lambda_strong_signal():
    tree, names, values = balanced_tree([0.0, 0.0, 10.0, 10.0])
    step = PhyloLambdaStep()
    ctx, out = run_step(step, {"output": "lambda"}, tree, trait_form(names, values))
    summary = step.export(ctx)
    assert 0.8 < summary["lambda"] <= 1.0
    assert summary["log_likelihood"] > summary["log_likelihood_lambda0"]


def test_lambda_no_signal():
    tree, names, values = balanced_tree([0.0, 10.0, 0.0, 10.0])
    step = PhyloLambdaStep()
    ctx, out = run_step(step, {"output": "lambda"}, tree, trait_form(names, values))
    summary = step.export(ctx)
    assert summary["lambda"] < 0.5


def test_ancestral_root_is_gls_mean():
    a, b, c = leaf("A", 1.0), leaf("B", 1.0), leaf("C", 1.0)
    root = join("R", [(a, 1.0), (b, 1.0), (c, 1.0)])
    tree = build_tree_form(root, "node", "field", "tree")
    step = PhyloAncestralStep()
    ctx, out = run_step(step, {"output": "ancestral"}, tree, trait_form(["A", "B", "C"], [0.0, 2.0, 4.0]))
    assert abs(step.export(ctx)["root_estimate"] - 2.0) < 1e-9
    labels = out.labels["node"]
    assert "R" in labels
    assert out.data.shape == (1, 2)


def test_ancestral_missing_trait():
    tree, names, values = balanced_tree([0.0, 1.0, 2.0, 3.0])
    step = PhyloAncestralStep()
    with pytest.raises(StepError, match="missing"):
        run_step(step, {"output": "ancestral"}, tree, trait_form(names[:3], values[:3]))


def test_extra_trait_sample_rejected():
    tree, names, values = balanced_tree([0.0, 1.0, 2.0, 3.0])
    step = PhyloLambdaStep()
    with pytest.raises(StepError, match="not tree tips"):
        run_step(step, {"output": "lambda"}, tree,
                 trait_form(names + ["Z"], values + [0.5]))


def test_missing_value_column():
    tree, names, values = balanced_tree([0.0, 1.0, 2.0, 3.0])
    step = PhyloLambdaStep()
    with pytest.raises(StepError, match="no 'size' column"):
        run_step(step, {"output": "lambda", "value_field": "size"}, tree,
                 trait_form(names, values))
