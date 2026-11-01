"""Tests for the 1.3.0 phylogeny-aware operators and the PhyloXML reader."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest

from src.core import Form, ReaderError, StepError
from src.reader import pick_reader
from src.reader.readers.newick_reader import NewickReader
from src.reader.readers.phyloxml_reader import PhyloXmlReader
from src.task.step.steps.faith_pd import FaithPdStep
from src.task.step.steps.patristic_distance import PatristicDistanceStep
from src.task.step.steps.unweighted_unifrac import UnweightedUnifracStep
from src.task.step.steps.weighted_unifrac import WeightedUnifracStep


TREE = "(((A:0.1,B:0.2):0.3,C:0.4):0.5,D:0.6);"
TAXA = ["A", "B", "C", "D"]
COUNTS = [[1, 0, 2, 0], [0, 3, 0, 1]]

PHYLO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<phyloxml xmlns="http://www.phyloxml.org">
  <phylogeny rooted="true">
    <clade>
      <clade branch_length="0.3">
        <clade branch_length="0.1"><name>A</name></clade>
        <clade branch_length="0.2"><name>B</name></clade>
      </clade>
      <clade branch_length="0.4"><name>C</name></clade>
      <clade branch_length="0.6"><name>D</name></clade>
    </clade>
  </phylogeny>
</phyloxml>
"""


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _labels(names):
    return {name: index for index, name in enumerate(names)}


def _form(data, dims, labels):
    return Form(data=np.asarray(data, dtype=np.float32), dims=dims, labels=labels,
                info={"missing_code": np.nan})


def _counts_form(data, samples=("s1", "s2"), taxa=TAXA):
    return _form(data, ["sample", "taxon"],
                 {"sample": _labels(samples), "taxon": _labels(taxa)})


def _tree_form(tmp_path: Path, text: str = TREE) -> Form:
    path = tmp_path / "tree.nwk"
    path.write_text(text)
    return NewickReader().read(path, ["node", "field"], {"node": "builtin", "field": "builtin"})


def _phyloxml_form(tmp_path: Path, text: str = PHYLO_XML) -> Form:
    path = tmp_path / "tree.phyloxml"
    path.write_text(text)
    return PhyloXmlReader().read(path, ["node", "field"], {"node": "builtin", "field": "builtin"})


def _skbio(metric: str, counts, taxa=TAXA, tree_text: str = TREE):
    from skbio import TreeNode
    from skbio.diversity import alpha_diversity, beta_diversity

    tree = TreeNode.read(io.StringIO(tree_text))
    ids = [f"s{index}" for index in range(len(counts))]
    if metric in {"faith_pd"}:
        return np.asarray(alpha_diversity(metric, counts, ids=ids, taxa=taxa, tree=tree),
                          dtype=float)
    return np.asarray(beta_diversity(metric, counts, ids=ids, taxa=taxa, tree=tree).data,
                      dtype=float)


# --------------------------------------------------------------------------- Faith PD


def test_faith_pd_matches_skbio(tmp_path):
    out, exported = _run(
        FaithPdStep(),
        {"sample_dim": "sample", "taxon_dim": "taxon", "output": "out"},
        [_counts_form(COUNTS), _tree_form(tmp_path)],
    )
    assert out.dims == ["sample", "statistic"]
    assert list(out.labels["statistic"]) == ["pd", "n_taxa_observed", "n_tips"]
    expected = _skbio("faith_pd", COUNTS)
    np.testing.assert_allclose(out.data[:, 0], expected, atol=1e-6)
    np.testing.assert_allclose(out.data[:, 1], [2, 2])
    np.testing.assert_allclose(out.data[:, 2], [4, 4])
    assert out.info["representation"] == "faith_pd"
    assert exported["n_tips"] == 4
    assert exported["max_pd"] == pytest.approx(1.6, abs=1e-6)


def test_faith_pd_zero_sample(tmp_path):
    out, _ = _run(
        FaithPdStep(),
        {"sample_dim": "sample", "taxon_dim": "taxon", "output": "out"},
        [_counts_form([[0, 0, 0, 0], [1, 0, 2, 0]]), _tree_form(tmp_path)],
    )
    np.testing.assert_allclose(out.data[:, 0], [0.0, 1.3], atol=1e-6)


def test_faith_pd_rejects_taxon_not_tip(tmp_path):
    with pytest.raises(StepError, match="not tips"):
        _run(
            FaithPdStep(),
            {"sample_dim": "sample", "taxon_dim": "taxon", "output": "out"},
            [_counts_form([[1, 0, 2, 0], [0, 3, 0, 1]], taxa=["A", "B", "C", "X"]),
             _tree_form(tmp_path)],
        )


# --------------------------------------------------------------------------- UniFrac


def test_unweighted_unifrac_matches_skbio(tmp_path):
    out, exported = _run(
        UnweightedUnifracStep(),
        {"sample_dim": "sample", "taxon_dim": "taxon", "output": "out"},
        [_counts_form(COUNTS), _tree_form(tmp_path)],
    )
    assert out.dims == ["sample", "sample_b"]
    assert list(out.labels["sample"]) == ["s1", "s2"]
    expected = _skbio("unweighted_unifrac", COUNTS)
    np.testing.assert_allclose(out.data, expected, atol=1e-6)
    np.testing.assert_allclose(out.data, out.data.T)
    np.testing.assert_allclose(np.diag(out.data), 0.0)
    assert out.info["representation"] == "unweighted_unifrac"
    assert exported["n_samples"] == 2


def test_weighted_unifrac_matches_skbio(tmp_path):
    out, exported = _run(
        WeightedUnifracStep(),
        {"sample_dim": "sample", "taxon_dim": "taxon", "output": "out"},
        [_counts_form(COUNTS), _tree_form(tmp_path)],
    )
    expected = _skbio("weighted_unifrac", COUNTS)
    np.testing.assert_allclose(out.data, expected, atol=1e-6)
    assert out.data[0, 1] == pytest.approx(0.85, abs=1e-6)
    assert exported["max"] == pytest.approx(0.85, abs=1e-6)


def test_unifrac_zero_sample(tmp_path):
    counts = [[0, 0, 0, 0], [1, 0, 2, 0]]
    tree = _tree_form(tmp_path)
    uu, _ = _run(
        UnweightedUnifracStep(),
        {"sample_dim": "sample", "taxon_dim": "taxon", "output": "out"},
        [_counts_form(counts), tree],
    )
    wu, _ = _run(
        WeightedUnifracStep(),
        {"sample_dim": "sample", "taxon_dim": "taxon", "output": "out"},
        [_counts_form(counts), tree],
    )
    assert uu.data[0, 1] == pytest.approx(1.0)
    assert wu.data[0, 1] == pytest.approx(0.9)


def test_unifrac_requires_two_samples(tmp_path):
    with pytest.raises(StepError, match="at least two samples"):
        _run(
            WeightedUnifracStep(),
            {"sample_dim": "sample", "taxon_dim": "taxon", "output": "out"},
            [_counts_form([[1, 0, 2, 0]], samples=("s1",)), _tree_form(tmp_path)],
        )


# ---------------------------------------------------------------------- patristic


def test_patristic_distance_matches_skbio(tmp_path):
    out, exported = _run(
        PatristicDistanceStep(),
        {"node_dim": "node", "field_dim": "field", "tip_dim": "tip", "output": "out"},
        [_tree_form(tmp_path)],
    )
    tips = ["A", "B", "C", "D"]
    assert out.dims == ["tip", "tip_b"]
    assert list(out.labels["tip"]) == tips
    assert list(out.labels["tip_b"]) == tips
    from skbio import TreeNode

    tree = TreeNode.read(io.StringIO(TREE))
    reference = np.asarray(tree.tip_tip_distances().data, dtype=float)
    np.testing.assert_allclose(out.data, reference, atol=1e-6)
    assert exported["n_tips"] == 4
    assert exported["max"] == pytest.approx(1.6, abs=1e-6)


def test_patristic_distance_needs_two_tips(tmp_path):
    with pytest.raises(StepError, match="at least two tips"):
        _run(
            PatristicDistanceStep(),
            {"node_dim": "node", "field_dim": "field", "tip_dim": "tip", "output": "out"},
            [_tree_form(tmp_path, "(A:0.1);")],
        )


# ---------------------------------------------------------------------- PhyloXML


def test_phyloxml_reader_matches_newick_reader(tmp_path):
    form = _phyloxml_form(tmp_path)
    assert form.dims == ["node", "field"]
    assert list(form.labels["field"]) == ["parent", "branch_length", "depth", "is_leaf"]
    assert list(form.labels["node"]) == ["Internal0", "Internal1", "A", "B", "C", "D"]
    assert form.data[1, 1] == pytest.approx(0.3)
    assert form.data[2, 1] == pytest.approx(0.1)
    assert np.isnan(form.data[0, 1])
    assert list(form.data[:, 3]) == [0, 0, 1, 1, 1, 1]


def test_phyloxml_patristic_matches_biopython(tmp_path):
    form = _phyloxml_form(tmp_path)
    out, _ = _run(
        PatristicDistanceStep(),
        {"node_dim": "node", "field_dim": "field", "tip_dim": "tip", "output": "out"},
        [form],
    )
    from Bio import Phylo

    bio_tree = Phylo.read(tmp_path / "tree.phyloxml", "phyloxml")
    terminals = bio_tree.get_terminals()
    names = [name for name, _ in sorted(out.labels["tip"].items(), key=lambda item: item[1])]
    assert [clade.name for clade in terminals] == names
    for i, left in enumerate(terminals):
        for j, right in enumerate(terminals):
            expected = 0.0 if i == j else bio_tree.distance(left, right)
            assert out.data[i, j] == pytest.approx(expected, abs=1e-6)


def test_phyloxml_reader_dispatches_on_extension(tmp_path):
    path = tmp_path / "example.phyloxml"
    path.write_text(PHYLO_XML)
    assert isinstance(pick_reader(path).implementation(), PhyloXmlReader)


def test_phyloxml_reader_rejects_unnamed_tip(tmp_path):
    text = """<?xml version="1.0"?>
<phyloxml xmlns="http://www.phyloxml.org">
  <phylogeny>
    <clade>
      <clade branch_length="0.1"><name>A</name></clade>
      <clade branch_length="0.2"/>
    </clade>
  </phylogeny>
</phyloxml>
"""
    with pytest.raises(ReaderError, match="tip clade has no name"):
        _phyloxml_form(tmp_path, text)


def test_phyloxml_reader_rejects_multiple_phylogenies(tmp_path):
    text = """<?xml version="1.0"?>
<phyloxml xmlns="http://www.phyloxml.org">
  <phylogeny><clade branch_length="0.1"><name>A</name></clade></phylogeny>
  <phylogeny><clade branch_length="0.1"><name>B</name></clade></phylogeny>
</phyloxml>
"""
    with pytest.raises(ReaderError, match="exactly one phylogeny"):
        _phyloxml_form(tmp_path, text)


def test_phyloxml_reader_rejects_missing_clade(tmp_path):
    text = """<?xml version="1.0"?>
<phyloxml xmlns="http://www.phyloxml.org">
  <phylogeny rooted="true"></phylogeny>
</phyloxml>
"""
    with pytest.raises(ReaderError, match="no clade"):
        _phyloxml_form(tmp_path, text)


def test_phyloxml_reader_rejects_invalid_branch_length(tmp_path):
    text = """<?xml version="1.0"?>
<phyloxml xmlns="http://www.phyloxml.org">
  <phylogeny>
    <clade>
      <clade branch_length="nan?"><name>A</name></clade>
      <clade branch_length="0.2"><name>B</name></clade>
    </clade>
  </phylogeny>
</phyloxml>
"""
    with pytest.raises(ReaderError, match="invalid branch_length"):
        _phyloxml_form(tmp_path, text)
