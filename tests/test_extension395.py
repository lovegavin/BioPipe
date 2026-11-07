"""Contract tests for bootstrap support operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps._phylo_support_utils import split_label
from src.task.step.steps._tree_build_common import TreeNode, build_tree_form
from src.task.step.steps.phylo_bootstrap import PhyloBootstrapStep
from src.task.step.steps.phylo_support_filter import PhyloSupportFilterStep
from src.task.step.steps.phylo_support_summary import PhyloSupportSummaryStep


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


def tree_form():
    a, b, c, d = leaf("A", 0.1), leaf("B", 0.1), leaf("C", 0.1), leaf("D", 0.1)
    ab = join("N1", [(a, 0.1), (b, 0.1)])
    cd = join("N2", [(c, 0.1), (d, 0.1)])
    root = join("R", [(ab, 0.2), (cd, 0.2)])
    return build_tree_form(root, "node", "field", "tree")


def support_form(value, label="A|B"):
    data = np.asarray([[value]], dtype=np.float64)
    return Form(data, dims=["split", "statistic"],
                labels={"split": {label: 0}, "statistic": {"support": 0}})


def alignment_form():
    sequences = [
        "ACGT" * 20,
        "ACGT" * 20,
        "ACGA" * 20,
        "ACGA" * 20,
    ]
    names = ["A", "B", "C", "D"]
    length = len(sequences[0])
    data = np.zeros((len(sequences), length), dtype=np.float64)
    for row, sequence in enumerate(sequences):
        for column, base in enumerate(sequence):
            data[row, column] = "ACGT".index(base)
    return Form(data, dims=["sequence", "position"],
                labels={"sequence": {name: index for index, name in enumerate(names)},
                        "position": {str(index): index for index in range(length)}},
                info={"sequences": sequences}, axis_info=None)


def run(step, params, inputs):
    step.name = step.definition["id"]
    ctx = Ctx(**params)
    step.run(ctx, inputs)
    return ctx, ctx.outputs[params.get("output", "tree")]


def test_split_label_uses_smaller_side():
    tips = ["A", "B", "C", "D"]
    assert split_label({"A", "B"}, tips) == "A|B"
    assert split_label({"C", "D"}, tips) == "A|B"
    assert split_label({"A", "B", "C"}, tips) == "D"


def test_bootstrap_reports_support_values():
    form = alignment_form()
    step = PhyloBootstrapStep()
    ctx, out = run(step, {"resamples": 20, "seed": 1, "output": "bootstrap"}, [form])
    values = out.data[:, 0]
    assert values.size >= 1
    assert np.all(values >= 0.0) and np.all(values <= 1.0)
    assert out.info["n_resamples"] == 20


def test_bootstrap_is_deterministic_for_seed():
    form = alignment_form()
    step = PhyloBootstrapStep()
    _, first = run(step, {"resamples": 10, "seed": 7, "output": "bootstrap"}, [form])
    _, second = run(PhyloBootstrapStep(), {"resamples": 10, "seed": 7, "output": "bootstrap"}, [form])
    assert np.array_equal(first.data, second.data)


def test_filter_collapses_low_support():
    step = PhyloSupportFilterStep()
    ctx, out = run(step, {"min_support": 0.5, "output": "tree"},
                   [tree_form(), support_form(0.2)])
    # Both children of the root encode the same bipartition A|B, so both collapse.
    assert len(out.labels["node"]) == 5
    assert out.info["n_collapsed"] == 2


def test_filter_keeps_supported_split():
    step = PhyloSupportFilterStep()
    with pytest.raises(StepError, match="no split is below the threshold"):
        run(step, {"min_support": 0.5}, [tree_form(), support_form(0.9)])


def test_filter_threshold_zero_raises():
    step = PhyloSupportFilterStep()
    with pytest.raises(StepError, match="no split is below the threshold"):
        run(step, {"min_support": 0.0}, [tree_form(), support_form(0.2)])


def test_support_summary_counts():
    data = np.asarray([[0.2], [0.9]], dtype=np.float64)
    form = Form(data, dims=["split", "statistic"],
                 labels={"split": {"A|B": 0, "C|D": 1}, "statistic": {"support": 0}})
    step = PhyloSupportSummaryStep()
    ctx, out = run(step, {"threshold": 0.5, "output": "summary"}, [form])
    mapping = {name: float(out.data[index, 0])
               for name, index in out.labels["statistic"].items()
               if name != "value"}
    assert mapping["n_splits"] == 2
    assert mapping["mean_support"] == pytest.approx(0.55)
    assert mapping["n_below_threshold"] == 1


def test_support_summary_rejects_missing_column():
    data = np.asarray([[0.2]], dtype=np.float64)
    form = Form(data, dims=["split", "statistic"],
                 labels={"split": {"A|B": 0}, "statistic": {"value": 0}})
    step = PhyloSupportSummaryStep()
    with pytest.raises(StepError, match="support column"):
        run(step, {"threshold": 0.5}, [form])
