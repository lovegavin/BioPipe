from __future__ import annotations

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.aldex2 import Aldex2Step
from src.task.step.steps.ancom_bc import AncomBcStep
from src.task.step.steps.gsea import GseaStep
from src.task.step.steps.limma_de import LimmaDeStep
from src.task.step.steps.meta_analysis import MetaAnalysisStep
from src.task.step.steps.ora import OraStep
from src.task.step.steps.protein_rollup import ProteinRollupStep
from src.task.step.steps.prs import PrsStep
from src.task.step.steps.pseudobulk import PseudobulkStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def form(data, dims, labels):
    value = Form(np.asarray(data, dtype=np.float32), list(dims), labels,
                 {"missing_code": np.nan})
    value.validate()
    return value


def run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    key = params.get("output", step.name)
    return ctx[key], step.export(ctx)


def meta_form(data, dims, labels):
    value = Form(np.asarray(data, dtype=object), list(dims), labels,
                 {"missing_code": np.nan})
    value.validate()
    return value


def stat_form(data, genes, columns):
    return form(data, ["gene", "statistic"],
                {"gene": {g: i for i, g in enumerate(genes)},
                 "statistic": {c: i for i, c in enumerate(columns)}})


def set_form(data, genes, sets):
    return form(data, ["gene", "gene_set"],
                {"gene": {g: i for i, g in enumerate(genes)},
                 "gene_set": {s: i for i, s in enumerate(sets)}})


def test_ora_hypergeometric_and_columns():
    genes = [f"g{i}" for i in range(20)]
    stats = [[0.0, 0.01] if i < 5 else [0.0, 0.5] for i in range(20)]
    sets = np.zeros((20, 2), dtype=np.float32)
    sets[:5, 0] = 1
    sets[10:15, 1] = 1
    out, export = run(
        OraStep(),
        {"p_label": "Q_VALUE", "lfc_label": "log2FC", "p_threshold": 0.05,
         "lfc_threshold": 0.0, "output": "ora"},
        [stat_form(stats, genes, ["log2FC", "Q_VALUE"]),
         set_form(sets, genes, ["A", "B"])],
    )
    assert out.dims == ["gene_set", "statistic"]
    assert out.labels["statistic"]["P_VALUE"] == 3
    assert export["hits"] == 5
    assert export["results"][0]["n_hit"] == 5
    assert export["results"][0]["P_VALUE"] < 0.01


def test_pseudobulk_sum_and_mean():
    counts = np.array([[1, 2], [3, 4], [10, 20], [30, 40]], dtype=np.float32)
    counts_form = form(counts, ["cell", "gene"],
                       {"cell": {f"c{i}": i for i in range(4)},
                        "gene": {"a": 0, "b": 1}})
    meta = meta_form(np.array([["a"], ["a"], ["b"], ["b"]], dtype=object),
                     ["cell", "feature"],
                     {"cell": {f"c{i}": i for i in range(4)}, "feature": {"group": 0}})
    out, export = run(PseudobulkStep(), {"group_label": "group", "method": "sum"}, [counts_form, meta])
    assert out.data.tolist() == [[4.0, 6.0], [40.0, 60.0]]
    assert export["cells_per_group"] == {"a": 2, "b": 2}


def test_meta_analysis_fixed_and_random():
    effects = form([[0.2, 0.4]], ["variant", "study"],
                   {"variant": {"v1": 0}, "study": {"s1": 0, "s2": 1}})
    stds = form([[0.1, 0.2]], ["variant", "study"],
                {"variant": {"v1": 0}, "study": {"s1": 0, "s2": 1}})
    out, _ = run(MetaAnalysisStep(), {"method": "fixed"}, [effects, stds])
    assert out.labels["statistic"]["beta"] == 0
    assert out.data[0, 0] == pytest.approx(0.24, rel=1e-6)
    assert out.data[0, 0] == pytest.approx(0.24, rel=1e-6)


def test_meta_analysis_label_mapping_order_is_ignored():
    effects = form([[0.2, 0.4], [0.1, 0.3]], ["variant", "study"],
                   {"variant": {"v1": 0, "v2": 1}, "study": {"s1": 0, "s2": 1}})
    stds = form([[0.1, 0.2], [0.1, 0.2]], ["variant", "study"],
                {"variant": {"v2": 1, "v1": 0}, "study": {"s2": 1, "s1": 0}})
    out, _ = run(MetaAnalysisStep(), {"method": "fixed"}, [effects, stds])
    assert out.labels["variant"] == {"v1": 0, "v2": 1}
    assert out.data[0, 0] == pytest.approx(0.24, rel=1e-6)


def test_prs_hand_calculated():
    geno = form([[0, 1], [2, 0]], ["variant", "sample"],
                {"variant": {"v1": 0, "v2": 1}, "sample": {"s1": 0, "s2": 1}})
    weights = form([[0.5], [-1.0]], ["variant", "statistic"],
                   {"variant": {"v1": 0, "v2": 1}, "statistic": {"beta": 0}})
    out, _ = run(PrsStep(), {"weight_label": "beta"}, [geno, weights])
    assert out.data[:, 0].tolist() == pytest.approx([-2.0, 0.5])
    assert out.data[:, 1].tolist() == [2.0, 2.0]


def test_protein_rollup_shared_peptides():
    peptides = form([[1, 2], [3, 4], [10, 20]], ["peptide", "sample"],
                    {"peptide": {"p1": 0, "p2": 1, "p3": 2},
                     "sample": {"s1": 0, "s2": 1}})
    mapping = form([[1, 0], [1, 1], [0, 1]], ["peptide", "protein"],
                   {"peptide": {"p1": 0, "p2": 1, "p3": 2},
                    "protein": {"prot1": 0, "prot2": 1}})
    out, export = run(ProteinRollupStep(), {"min_peptides": 1}, [peptides, mapping])
    assert out.data.tolist() == [[4.0, 6.0], [13.0, 24.0]]
    assert export["proteins"] == 2


def test_gsea_top_set_has_positive_score():
    genes = [f"g{i}" for i in range(20)]
    stats = [[20 - i, 0.01] for i in range(20)]
    sets = np.zeros((20, 1), dtype=np.float32)
    sets[:4, 0] = 1
    out, export = run(
        GseaStep(),
        {"rank_label": "log2FC", "n_permutations": 50, "min_set_size": 3,
         "max_set_size": 10, "seed": 3, "output": "gsea"},
        [stat_form(stats, genes, ["log2FC", "Q_VALUE"]), set_form(sets, genes, ["TOP"])],
    )
    assert export["sets_tested"] == 1
    assert out.data[0, 0] > 0
    assert 0 <= out.data[0, 2] <= 1


def test_differential_abundance_outputs():
    counts = form(np.array([[10, 2], [12, 1], [11, 3], [30, 10], [28, 8], [32, 9]], dtype=np.float32),
                  ["sample", "taxon"],
                  {"sample": {f"s{i}": i for i in range(6)}, "taxon": {"t1": 0, "t2": 1}})
    meta = meta_form(np.array([["a"], ["a"], ["a"], ["b"], ["b"], ["b"]], dtype=object),
                     ["sample", "feature"],
                     {"sample": {f"s{i}": i for i in range(6)}, "feature": {"group": 0}})
    for cls in (Aldex2Step, AncomBcStep):
        out, export = run(cls(), {"group_label": "group", "group_a": "a", "group_b": "b",
                                  "n_mc": 8, "output": "da"}, [counts, meta])
        assert out.data.shape == (2, 7 if cls is Aldex2Step else 6)
        assert export["n_a"] == 3 and export["n_b"] == 3


def test_limma_hand_calculated_balanced_groups():
    data = np.array([[1, 2, 1, 5, 6, 5]], dtype=np.float32)
    values = form(data, ["protein", "sample"],
                  {"protein": {"p1": 0},
                   "sample": {f"s{i}": i for i in range(6)}})
    meta = meta_form(np.array([["a"], ["a"], ["a"], ["b"], ["b"], ["b"]], dtype=object),
                     ["sample", "feature"],
                     {"sample": {f"s{i}": i for i in range(6)}, "feature": {"group": 0}})
    out, _ = run(LimmaDeStep(), {"feature_dim": "protein", "sample_dim": "sample",
                                 "group_label": "group", "group_a": "a", "group_b": "b",
                                 "prior_df": 0}, [values, meta])
    assert out.data[0, 0] == pytest.approx(4.0, rel=1e-6)
    assert out.data[0, 4] < 0.01


def test_scanpy_doublet_and_marker_score():
    pytest.importorskip("scanpy")
    from src.task.step.steps.doublet_detect import DoubletDetectStep
    from src.task.step.steps.marker_score import MarkerScoreStep
    rng = np.random.default_rng(11)
    ncell, ngene = 100, 60
    counts = rng.poisson(1.0, (ncell, ngene)).astype(np.float32)
    expr = form(counts, ["cell", "gene"],
                {"cell": {f"c{i}": i for i in range(ncell)},
                 "gene": {f"g{i}": i for i in range(ngene)}})
    doublets, export = run(
        DoubletDetectStep(),
        {"cell_dim": "cell", "gene_dim": "gene", "n_prin_comps": 10, "output": "doublets"},
        [expr],
    )
    assert doublets.data.shape == (ncell, 3)
    assert export["n_cells"] == ncell

    members = np.zeros((ngene, 2), dtype=np.float32)
    members[:10, 0] = 1
    members[20:30, 1] = 1
    gene_sets = form(members, ["gene", "gene_set"],
                     {"gene": {f"g{i}": i for i in range(ngene)},
                      "gene_set": {"A": 0, "B": 1}})
    scores, export = run(
        MarkerScoreStep(),
        {"cell_dim": "cell", "gene_dim": "gene", "gene_set_dim": "gene_set",
         "min_genes": 5, "ctrl_size": 20, "n_bins": 10, "output": "scores"},
        [expr, gene_sets],
    )
    assert scores.data.shape == (ncell, 2)
    assert export["sets_scored"] == ["A", "B"]
