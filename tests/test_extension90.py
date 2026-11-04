"""Tests for the 1.5.0 tree builders, Robinson-Foulds and PLAGE."""
from __future__ import annotations

from io import StringIO

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers.newick_reader import NewickReader
from src.task.step.steps._phylo_common import load_tree, tip_distances
from src.task.step.steps.gsva_plage import GsvaPlageStep
from src.task.step.steps.neighbor_joining import NeighborJoiningStep
from src.task.step.steps.robinson_foulds import RobinsonFouldsStep
from src.task.step.steps.upgma import UpgmaStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, list(inputs))
    return ctx[params.get("output", "output")], step.export(ctx)


def _distance_form(names, matrix):
    data = np.asarray(matrix, dtype=np.float64)
    return Form(
        data=data.astype(np.float32),
        dims=["taxon", "taxon_b"],
        labels={
            "taxon": {name: i for i, name in enumerate(names)},
            "taxon_b": {name: i for i, name in enumerate(names)},
        },
        info={"missing_code": np.nan},
    )


def _tree_distances(tree_form, names):
    loaded = load_tree(tree_form)
    tips = [loaded.names[index] for index in loaded.tips]
    matrix = tip_distances(loaded)
    return np.array(
        [[matrix[tips.index(a), tips.index(b)] for b in names] for a in names],
        dtype=np.float64,
    )


def _biopython_tree(newick):
    pytest.importorskip("Bio")
    from Bio import Phylo

    return Phylo.read(StringIO(newick), "newick")


def _bio_matrix(tree, names):
    return np.array([[tree.distance(a, b) for b in names] for a in names], dtype=np.float64)


def test_neighbor_joining_recovers_additive_distances():
    tree = _biopython_tree("(((A:1,B:2):1,C:3):1,(D:1,E:1):1);")
    names = [tip.name for tip in tree.get_terminals()]
    expected = _bio_matrix(tree, names)
    form = _distance_form(names, expected)
    out, export = _run(NeighborJoiningStep(), {"output": "output"}, [form])
    assert out.dims == ["node", "field"]
    assert export["n_taxa"] == 5
    ours = _tree_distances(out, names)
    assert np.allclose(ours, expected, atol=1e-6)
    assert np.allclose(ours, ours.T, atol=1e-6)


def test_neighbor_joining_is_deterministic_and_rooted():
    names = ["A", "B", "C", "D"]
    matrix = np.array(
        [[0, 5, 9, 9], [5, 0, 10, 10], [9, 10, 0, 8], [9, 10, 8, 0]], dtype=float
    )
    first, _ = _run(NeighborJoiningStep(), {"output": "output"}, [_distance_form(names, matrix)])
    second, _ = _run(NeighborJoiningStep(), {"output": "output"}, [_distance_form(names, matrix)])
    assert np.array_equal(first.data, second.data, equal_nan=True)
    loaded = load_tree(first)
    assert loaded.root >= 0
    assert len(loaded.tips) == 4


def test_upgma_recovers_ultrametric_tree():
    names = ["A", "B", "C", "D"]
    matrix = np.array(
        [[0, 2, 6, 6], [2, 0, 6, 6], [6, 6, 0, 4], [6, 6, 4, 0]], dtype=float
    )
    out, export = _run(UpgmaStep(), {"output": "output"}, [_distance_form(names, matrix)])
    assert export["negative_branches_clipped"] == 0
    assert np.allclose(_tree_distances(out, names), matrix, atol=1e-6)
    loaded = load_tree(out)
    lengths = {loaded.names[index]: loaded.length[index] for index in range(len(loaded.names))}
    assert lengths["A"] == pytest.approx(1.0, abs=1e-6)
    assert lengths["B"] == pytest.approx(1.0, abs=1e-6)
    assert lengths["C"] == pytest.approx(2.0, abs=1e-6)
    assert lengths["D"] == pytest.approx(2.0, abs=1e-6)


def test_tree_builders_reject_bad_matrices():
    names = ["A", "B"]
    with pytest.raises(StepError, match="symmetric"):
        _run(NeighborJoiningStep(), {"output": "output"},
             [_distance_form(names, np.array([[0.0, 1.0], [2.0, 0.0]]))])
    with pytest.raises(StepError, match="diagonal"):
        _run(NeighborJoiningStep(), {"output": "output"},
             [_distance_form(names, np.array([[1.0, 1.0], [1.0, 0.0]]))])
    with pytest.raises(StepError, match="nonnegative"):
        _run(UpgmaStep(), {"output": "output"},
             [_distance_form(names, np.array([[0.0, -1.0], [-1.0, 0.0]]))])
    with pytest.raises(StepError, match="at least two taxa"):
        _run(UpgmaStep(), {"output": "output"}, [_distance_form(["A"], np.zeros((1, 1)))])


def _newick_form(tmp_path, filename, text):
    path = tmp_path / filename
    path.write_text(text, encoding="utf-8")
    return NewickReader().read(path, ["node", "field"], {})


def _statistic_map(form):
    names = [name for name, _ in sorted(form.labels["statistic"].items(), key=lambda item: item[1])]
    return dict(zip(names, form.data[:, 0]))


def test_robinson_foulds_matches_dendropy(tmp_path):
    dendropy = pytest.importorskip("dendropy")
    treecompare = pytest.importorskip("dendropy.calculate.treecompare")
    first = "((A:1,B:1):1,(C:1,D:1):1);"
    second = "((A:1,C:1):1,(B:1,D:1):1);"
    form_a = _newick_form(tmp_path, "a.nwk", first)
    form_b = _newick_form(tmp_path, "b.nwk", second)
    out, export = _run(RobinsonFouldsStep(), {"output": "output"}, [form_a, form_b])
    namespace = dendropy.TaxonNamespace()
    left = dendropy.Tree.get(data=first, schema="newick", taxon_namespace=namespace)
    right = dendropy.Tree.get(data=second, schema="newick", taxon_namespace=namespace)
    expected = int(treecompare.unweighted_robinson_foulds_distance(left, right))
    assert export["rf"] == expected == 2
    stats = _statistic_map(out)
    assert stats["rf"] == pytest.approx(2.0)
    assert stats["max_rf"] == pytest.approx(2.0)
    assert stats["normalized_rf"] == pytest.approx(1.0)


def test_robinson_foulds_identical_trees(tmp_path):
    newick = "((A:1,B:1):1,(C:1,(D:1,E:1):1):1);"
    first = _newick_form(tmp_path, "a.nwk", newick)
    second = _newick_form(tmp_path, "b.nwk", newick)
    out, export = _run(RobinsonFouldsStep(), {"output": "output"}, [first, second])
    stats = _statistic_map(out)
    assert export["rf"] == 0
    assert stats["max_rf"] > 0
    assert stats["normalized_rf"] == pytest.approx(0.0)


def test_robinson_foulds_requires_same_taxa(tmp_path):
    first = _newick_form(tmp_path, "a.nwk", "((A:1,B:1):1,(C:1,D:1):1);")
    second = _newick_form(tmp_path, "b.nwk", "((A:1,B:1):1,(C:1,E:1):1);")
    with pytest.raises(StepError, match="same taxa"):
        _run(RobinsonFouldsStep(), {"output": "output"}, [first, second])


def _expression_form(matrix, genes, samples):
    data = np.asarray(matrix, dtype=np.float64)
    return Form(
        data=data.astype(np.float32),
        dims=["gene", "sample"],
        labels={
            "gene": {name: i for i, name in enumerate(genes)},
            "sample": {name: i for i, name in enumerate(samples)},
        },
        info={"missing_code": np.nan},
    )


def _sets_form(genes, set_names, members):
    data = np.zeros((len(genes), len(set_names)), dtype=np.float32)
    for column, items in enumerate(members):
        for gene in items:
            data[genes.index(gene), column] = 1.0
    return Form(
        data=data,
        dims=["gene", "gene_set"],
        labels={
            "gene": {name: i for i, name in enumerate(genes)},
            "gene_set": {name: i for i, name in enumerate(set_names)},
        },
        info={"missing_code": np.nan},
    )


def test_plage_two_gene_set_matches_first_singular_vector():
    rng = np.random.default_rng(7)
    genes = ["g1", "g2", "g3"]
    samples = ["s1", "s2", "s3", "s4", "s5"]
    data = rng.normal(size=(len(genes), len(samples)))
    expr = _expression_form(data, genes, samples)
    sets = _sets_form(genes, ["set1"], [["g1", "g2"]])
    out, export = _run(
        GsvaPlageStep(),
        {"output": "output", "feature_dim": "gene", "gene_set_dim": "gene_set"},
        [expr, sets],
    )
    block = data[:2]
    scaled = (block - block.mean(axis=1, keepdims=True)) / block.std(axis=1, ddof=1, keepdims=True)
    _, _, vh = np.linalg.svd(scaled, full_matrices=False)
    expected = np.asarray(vh[0], dtype=np.float64)
    if expected[int(np.argmax(np.abs(expected)))] < 0:
        expected = -expected
    assert out.dims == ["sample", "gene_set"]
    assert np.allclose(out.data[:, 0], expected, atol=1e-6)
    assert export["set_sizes"] == {"set1": 2}


def test_plage_single_gene_set_is_normalized_zscores():
    genes = ["g1", "g2", "g3"]
    samples = ["s1", "s2", "s3", "s4"]
    data = np.array([[1.0, 2.0, 4.0, 7.0], [0.5, 0.6, 0.4, 0.9], [2.0, 1.0, 3.0, 2.0]])
    expr = _expression_form(data, genes, samples)
    sets = _sets_form(genes, ["set1"], [["g2"]])
    out, _ = _run(
        GsvaPlageStep(),
        {"output": "output", "feature_dim": "gene", "gene_set_dim": "gene_set"},
        [expr, sets],
    )
    z = (data[1] - data[1].mean()) / data[1].std(ddof=1)
    expected = z / np.linalg.norm(z)
    if expected[int(np.argmax(np.abs(expected)))] < 0:
        expected = -expected
    assert np.allclose(out.data[:, 0], expected, atol=1e-6)


def test_plage_rejects_constant_gene():
    genes = ["g1", "g2", "g3"]
    samples = ["s1", "s2", "s3"]
    data = np.array([[1.0, 2.0, 3.0], [5.0, 5.0, 5.0], [3.0, 1.0, 2.0]])
    expr = _expression_form(data, genes, samples)
    sets = _sets_form(genes, ["set1"], [["g2"]])
    with pytest.raises(StepError, match="constant genes"):
        _run(
            GsvaPlageStep(),
            {"output": "output", "feature_dim": "gene", "gene_set_dim": "gene_set"},
            [expr, sets],
        )


def test_plage_min_size_and_nonfinite():
    genes = ["g1", "g2", "g3"]
    samples = ["s1", "s2", "s3"]
    data = np.array([[1.0, 2.0, 3.0], [2.0, 5.0, 4.0], [3.0, 1.0, 2.0]])
    expr = _expression_form(data, genes, samples)
    sets = _sets_form(genes, ["small"], [["g1"]])
    with pytest.raises(StepError, match="no gene set has at least 2"):
        _run(
            GsvaPlageStep(),
            {"output": "output", "feature_dim": "gene", "gene_set_dim": "gene_set",
             "min_size": 2},
            [expr, sets],
        )
    broken = data.copy()
    broken[0, 0] = np.nan
    expr_bad = _expression_form(broken, genes, samples)
    with pytest.raises(StepError, match="non-finite"):
        _run(
            GsvaPlageStep(),
            {"output": "output", "feature_dim": "gene", "gene_set_dim": "gene_set"},
            [expr_bad, sets],
        )


def test_plage_requires_two_samples():
    genes = ["g1", "g2"]
    expr = _expression_form(np.array([[1.0], [2.0]]), genes, ["s1"])
    sets = _sets_form(genes, ["set1"], [["g1"]])
    with pytest.raises(StepError, match="two samples"):
        _run(
            GsvaPlageStep(),
            {"output": "output", "feature_dim": "gene", "gene_set_dim": "gene_set"},
            [expr, sets],
        )
