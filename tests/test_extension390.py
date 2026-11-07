"""Numerical and contract tests for the tree manipulation operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import StepError
from src.task.step.steps._tree_build_common import TreeNode, build_tree_form
from src.task.step.steps.tree_balance import TreeBalanceStep
from src.task.step.steps.tree_prune_tips import TreePruneTipsStep
from src.task.step.steps.tree_root_midpoint import TreeRootMidpointStep


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


def form_of(root):
    return build_tree_form(root, "node", "field", "tree")


def _run(step, params, form):
    step.name = step.definition["id"]
    ctx = Ctx(**params)
    step.run(ctx, [form])
    return ctx, ctx.outputs[params.get("output", "tree")]


def test_prune_two_tips_keeps_lengths():
    a, b, c, d = leaf("A", 1.0), leaf("B", 1.0), leaf("C", 2.0), leaf("D", 2.0)
    ab = join("AB", [(a, 1.0), (b, 1.0)])
    cd = join("CD", [(c, 2.0), (d, 2.0)])
    root = join("R", [(ab, 1.0), (cd, 1.0)])

    step = TreePruneTipsStep()
    ctx, out = _run(step, {"tips": "C,D", "output": "tree"}, form_of(root))
    labels = out.labels["node"]
    assert set(labels) == {"A", "B", "AB"}
    assert step.export(ctx)["n_tips_after"] == 2
    assert abs(step.export(ctx)["total_branch_length"] - 2.0) < 1e-9


def test_prune_collapses_unary_root():
    a, b = leaf("A", 1.0), leaf("B", 3.0)
    inner = join("inner", [(a, 2.0)])
    root = join("R", [(inner, 0.5), (b, 3.0)])

    step = TreePruneTipsStep()
    _ctx, out = _run(step, {"tips": "A", "output": "tree"}, form_of(root))
    labels = out.labels["node"]
    assert set(labels) == {"B"}
    assert np.isnan(out.data[out.labels["node"]["B"], 1])


def test_prune_rejects_unknown_tip():
    a, b = leaf("A", 1.0), leaf("B", 1.0)
    root = join("R", [(a, 1.0), (b, 1.0)])
    step = TreePruneTipsStep()
    with pytest.raises(StepError, match="unknown tip"):
        _run(step, {"tips": "Z", "output": "tree"}, form_of(root))


def test_prune_rejects_removing_every_tip():
    a, b = leaf("A", 1.0), leaf("B", 1.0)
    root = join("R", [(a, 1.0), (b, 1.0)])
    step = TreePruneTipsStep()
    with pytest.raises(StepError, match="cannot remove every tip"):
        _run(step, {"tips": "A,B", "output": "tree"}, form_of(root))


def test_midpoint_lands_on_node():
    a, b = leaf("A", 1.0), leaf("B", 1.0)
    c, d = leaf("C", 3.0), leaf("D", 3.0)
    ab = join("AB", [(a, 1.0), (b, 1.0)])
    cd = join("CD", [(c, 3.0), (d, 3.0)])
    root = join("R", [(ab, 1.0), (cd, 1.0)])

    step = TreeRootMidpointStep()
    _ctx, out = _run(step, {"output": "tree"}, form_of(root))
    node_dim = out.dims[0]
    root_label = [name for name, index in out.labels[node_dim].items() if np.isnan(out.data[index, 1])]
    assert root_label == ["CD"]


def test_midpoint_splits_edge_and_preserves_distances():
    a, b = leaf("A", 4.0), leaf("B", 1.0)
    c, d = leaf("C", 1.0), leaf("D", 1.0)
    ab = join("AB", [(a, 4.0), (b, 1.0)])
    cd = join("CD", [(c, 1.0), (d, 1.0)])
    root = join("R", [(ab, 1.0), (cd, 1.0)])

    before = form_of(root)
    step = TreeRootMidpointStep()
    _ctx, out = _run(step, {"output": "tree"}, before)
    exported = step.export(_ctx)
    assert exported["n_nodes"] == 7
    assert abs(exported["max_root_to_tip"] - exported["diameter"] / 2.0) < 1e-9


def test_balance_bifurcating():
    a, b, c, d = leaf("A", 1.0), leaf("B", 1.0), leaf("C", 1.0), leaf("D", 1.0)
    ab = join("AB", [(a, 1.0), (b, 1.0)])
    cd = join("CD", [(c, 1.0), (d, 1.0)])
    root = join("R", [(ab, 1.0), (cd, 1.0)])

    step = TreeBalanceStep()
    ctx, out = _run(step, {"output": "stats"}, form_of(root))
    values = {name: float(out.data[index, 0]) for name, index in out.labels["statistic"].items()}
    assert values["n_tips"] == 4
    assert values["sackin"] == 8
    assert values["colless"] == 0
    assert values["cherries"] == 2
    assert out.info["binary"] is True


def test_balance_polytomy_has_no_colless():
    a, b, c, d = leaf("A", 1.0), leaf("B", 1.0), leaf("C", 1.0), leaf("D", 1.0)
    ab = join("AB", [(a, 1.0), (b, 1.0)])
    root = join("R", [(ab, 1.0), (c, 1.0), (d, 1.0)])

    step = TreeBalanceStep()
    _ctx, out = _run(step, {"output": "stats"}, form_of(root))
    names = set(out.labels["statistic"])
    assert names == {"n_tips", "n_internal", "sackin", "cherries"}
    assert out.info["binary"] is False
