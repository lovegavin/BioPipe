"""Phylogenetic operator tests (extension 379)."""

from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers.newick_reader import NewickReader
from src.task.step.steps._phylo_common import load_tree
from src.task.step.steps._phylo_infer import (
    distance_matrix,
    neighbor_joining,
    pair_distance,
    robinson_foulds,
    splits,
    usable_columns,
)
from src.task.step.steps.phylo_distance_matrix import PhyloDistanceMatrixStep
from src.task.step.steps.phylo_neighbor_joining import PhyloNeighborJoiningStep
from src.task.step.steps.phylo_tree_distance import PhylotreeDistanceStep


_CODES = {"A": 0, "C": 1, "G": 2, "T": 3, "N": 4}


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)


def _aligned(sequences, names=None):
    names = list(names or [f"taxon{index}" for index in range(len(sequences))])
    width = len(sequences[0])
    data = np.zeros((len(sequences), width), dtype=np.int64)
    for row, sequence in enumerate(sequences):
        for column, base in enumerate(sequence.upper()):
            data[row, column] = _CODES[base]
    return Form(
        data,
        dims=["sequence", "position"],
        labels={"sequence": {name: index for index, name in enumerate(names)}, "position": {}},
        info={"sequences": list(sequences), "alphabet_map": "ACGTN"},
    )


def _matrix(values):
    names = ["A", "B", "C", "D"]
    return Form(
        np.asarray(values, dtype=np.float64),
        dims=["taxon", "taxon_b"],
        labels={"taxon": {name: index for index, name in enumerate(names)},
                "taxon_b": {name: index for index, name in enumerate(names)}},
    )


def _tree(newick, tmp_path, tag="a"):
    path = tmp_path / f"tree_{tag}.nwk"
    path.write_text(newick, encoding="utf-8")
    return NewickReader().read(path, ["node", "field"], {"node": "builtin", "field": "builtin"})


def test_pair_distance_models_hand_values():
    assert pair_distance("ACGT", "ACGA", "p", "complete") == pytest.approx(0.25)
    assert pair_distance("ACGT", "ACGA", "jc69", "complete") == pytest.approx(
        -0.75 * np.log(1.0 - 4.0 / 3.0 * 0.25)
    )
    assert pair_distance("ACGT", "ACGA", "k2p", "complete") == pytest.approx(
        -0.5 * np.log(0.75) - 0.25 * np.log(0.5)
    )
    assert pair_distance("ACGT", "ACGA", "protein", "complete") == pytest.approx(0.25)


def test_usable_columns_complete_deletion():
    records = [("a", "ACGT"), ("b", "A-GT"), ("c", "AC-T")]
    assert usable_columns(records, "p") == [0, 3]
    assert usable_columns(records, "protein") == [0, 3]


def test_distance_matrix_is_symmetric():
    records = [("a", "ACGT"), ("b", "ACGA"), ("c", "TCGT")]
    matrix = distance_matrix(records, "p", "complete")
    assert matrix.shape == (3, 3)
    assert np.allclose(matrix, matrix.T)
    assert np.allclose(np.diag(matrix), 0.0)
    assert matrix[0, 1] == pytest.approx(0.25)
    assert matrix[0, 2] == pytest.approx(0.25)


def test_neighbor_joining_recovers_additive_tree(tmp_path):
    matrix = np.asarray(
        [[0, 2, 6, 6], [2, 0, 6, 6], [6, 6, 0, 2], [6, 6, 2, 0]], dtype=np.float64
    )
    edges, newick = neighbor_joining(matrix, ["A", "B", "C", "D"])
    assert newick.endswith(";")
    assert len(edges) == 7
    path = tmp_path / "nj.nwk"
    path.write_text(newick, encoding="utf-8")
    tree = load_tree(NewickReader().read(path, ["node", "field"], {"node": "builtin", "field": "builtin"}))
    assert set(tree.names[index] for index in tree.tips) == {"A", "B", "C", "D"}
    assert splits(tree) == {frozenset({"A", "B"}): pytest.approx(2.0)}
    total = sum(length for _, _, length in edges)
    assert total == pytest.approx(8.0)


def test_neighbor_joining_rejects_asymmetric():
    with pytest.raises(StepError, match="symmetric"):
        neighbor_joining(np.asarray([[0, 1], [2, 0]], dtype=float), ["A", "B"])


def test_robinson_foulds_identical_and_different(tmp_path):
    tree_a = load_tree(_tree("((A:1,B:1):2,(C:1,D:1):2);", tmp_path, "a"))
    tree_b = load_tree(_tree("((A:1,C:1):2,(B:1,D:1):2);", tmp_path, "b"))
    same = robinson_foulds(tree_a, tree_a)
    assert same["rf"] == 0
    assert same["normalized_rf"] == 0.0
    assert same["branch_score"] == 0.0
    assert same["identical"] is True
    different = robinson_foulds(tree_a, tree_b)
    assert different["rf"] == 2
    assert different["max_rf"] == 2
    assert different["normalized_rf"] == 1.0
    assert different["shared_splits"] == 0
    assert different["branch_score"] == pytest.approx(np.sqrt(8.0))


def test_distance_matrix_operator_square_form():
    form = _aligned(["ACGT", "ACGA", "TCGT"], ["a", "b", "c"])
    step = PhyloDistanceMatrixStep()
    ctx = Ctx({"output": "out", "model": "p"})
    step.run(ctx, [form])
    out = ctx["out"]
    assert list(out.dims) == ["taxon", "taxon_b"]
    assert out.labels["taxon"] == {"a": 0, "b": 1, "c": 2}
    assert out.data[0, 1] == pytest.approx(0.25)
    assert out.info["n_sequences"] == 3
    assert step.export(ctx)["n_sites"] == 4


def test_neighbor_joining_operator_roundtrip(tmp_path):
    form = _matrix([[0, 2, 6, 6], [2, 0, 6, 6], [6, 6, 0, 2], [6, 6, 2, 0]])
    step = PhyloNeighborJoiningStep()
    ctx = Ctx({"output": "tree"})
    step.run(ctx, [form])
    out = ctx["tree"]
    assert list(out.dims) == ["node", "field"]
    assert out.info["newick"].endswith(";")
    parsed = load_tree(out)
    assert len(parsed.tips) == 4
    assert step.export(ctx)["n_tips"] == 4


def test_tree_distance_operator_rows(tmp_path):
    form_a = _tree("((A:1,B:1):2,(C:1,D:1):2);", tmp_path, "a")
    form_b = _tree("((A:1,C:1):2,(B:1,D:1):2);", tmp_path, "b")
    step = PhylotreeDistanceStep()
    ctx = Ctx({"output": "distance"})
    step.run(ctx, [form_a, form_b])
    out = ctx["distance"]
    rows = {name: out.data[index, 0] for name, index in out.labels["statistic"].items()}
    assert rows["n_tips"] == 4
    assert rows["rf"] == 2
    assert rows["normalized_rf"] == 1.0
    assert rows["identical"] == 0.0
    assert out.info["branch_score"] == pytest.approx(np.sqrt(8.0))


def test_estimate_memory_contract():
    for step in (PhyloDistanceMatrixStep, PhyloNeighborJoiningStep, PhylotreeDistanceStep):
        workspace, output = step.estimate_memory([], {}, {})
        assert workspace > 0 and output >= 0


def test_distance_matrix_operator_keeps_float64_precision():
    # 361/1396 is not exactly representable in float32; a float32 Form would
    # shift the exported p-distance by about 1.5e-8 and every NJ branch length.
    same = "A" * 1396
    other = "C" * 361 + "A" * 1035
    form = _aligned([same, other, same], ["a", "b", "c"])
    step = PhyloDistanceMatrixStep()
    ctx = Ctx({"output": "out", "model": "p"})
    step.run(ctx, [form])
    out = ctx["out"]
    assert out.data.dtype == np.float64
    assert out.data[0, 1] == 361 / 1396
