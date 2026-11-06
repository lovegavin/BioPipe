"""Batch 4 trajectory operators: hand-built embeddings with exact values."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.steps.cell_communication import CellCommunicationStep, read_pairs
from src.task.step.steps.paga_connectivity import PagaConnectivityStep, paga_connectivity
from src.task.step.steps.pseudotime_dpt import PseudotimeDptStep, diffusion_pseudotime
from src.task.step.steps.trajectory_gene_trends import (
    TrajectoryGeneTrendsStep,
    gene_trends,
)


def _embedding(values, labels=None):
    data = np.asarray(values, dtype=float).reshape(len(values), -1)
    if labels is None:
        labels = [f"c{index}" for index in range(len(values))]
    return Form(
        data=data,
        dims=["cell", "component"],
        labels={"cell": {label: index for index, label in enumerate(labels)},
                "component": {f"PC{index}": index for index in range(data.shape[1])}},
    )


def _cluster_labels(clusters, cells=None):
    data = np.asarray(clusters, dtype=float).reshape(-1, 1)
    if cells is None:
        cells = [f"c{index}" for index in range(data.shape[0])]
    return Form(
        data=data,
        dims=["cell", "cluster"],
        labels={"cell": {label: index for index, label in enumerate(cells)},
                "cluster": {"cluster": 0}},
    )


def _expression(values, genes, cells):
    data = np.asarray(values, dtype=float)
    return Form(
        data=data,
        dims=["cell", "gene"],
        labels={"cell": {label: index for index, label in enumerate(cells)},
                "gene": {gene: index for index, gene in enumerate(genes)}},
    )


def _pseudotime(values, cells):
    data = np.asarray(values, dtype=float).reshape(-1, 1)
    return Form(
        data=data,
        dims=["cell", "pseudotime"],
        labels={"cell": {label: index for index, label in enumerate(cells)},
                "pseudotime": {"pseudotime": 0}},
    )


def _run(step, params, inputs, tmp_path):
    if getattr(step, "name", None) in (None, "", "unnamed"):
        step.name = step.definition["id"]
    ctx = Context(tmp_path / "task", {})
    ctx.step_params = dict(params)
    step.run(ctx, inputs)
    return ctx, step.export(ctx)


def test_diffusion_pseudotime_is_monotone_on_a_line():
    embedding = np.arange(6, dtype=float).reshape(-1, 1)
    dpt = diffusion_pseudotime(embedding, 0, n_neighbors=3, n_dcs=2)
    assert dpt[0] == pytest.approx(0.0, abs=1e-12)
    assert dpt.max() == pytest.approx(1.0)
    assert np.all(np.diff(dpt) > 0.0)
    assert np.all(np.isfinite(dpt))


def test_pseudotime_step_uses_named_root(tmp_path):
    form = _embedding(np.arange(6, dtype=float), labels=[f"cell{index}" for index in range(6)])
    ctx, exported = _run(
        PseudotimeDptStep(),
        {"root_cell": "cell3", "n_neighbors": 3, "n_dcs": 2, "output": "pseudotime"},
        [form],
        tmp_path,
    )
    result = ctx["pseudotime"]
    assert result.dims == ["cell", "pseudotime"]
    assert result.data.shape == (6, 1)
    assert result.labels["pseudotime"] == {"pseudotime": 0}
    assert result.data[int(result.labels["cell"]["cell3"]), 0] == pytest.approx(0.0)
    assert exported["n_cells"] == 6
    assert exported["pseudotime_max"] == pytest.approx(1.0)


def test_pseudotime_rejects_unknown_root(tmp_path):
    form = _embedding(np.arange(6, dtype=float))
    with pytest.raises(StepError, match="root cell"):
        _run(
            PseudotimeDptStep(),
            {"root_cell": "missing", "output": "pseudotime"},
            [form],
            tmp_path,
        )


def test_paga_separated_clusters_are_fully_connected():
    values = [[0.0, 0.0], [0.1, 0.0], [0.0, 0.1], [10.0, 10.0], [10.1, 10.0], [10.0, 10.1]]
    names, connectivity = paga_connectivity(values, ["0", "0", "0", "1", "1", "1"], n_neighbors=3)
    assert names == ["0", "1"]
    assert connectivity.shape == (2, 2)
    assert connectivity[0, 0] == 0.0 and connectivity[1, 1] == 0.0
    assert connectivity[0, 1] == pytest.approx(1.0)
    assert connectivity[1, 0] == pytest.approx(1.0)


def test_paga_does_not_link_distant_clusters():
    values = [[float(index), 0.0] for index in range(9)] + [[100.0 + index, 0.0] for index in range(9)]
    clusters = ["0"] * 9 + ["2"] * 9
    names, connectivity = paga_connectivity(values, clusters, n_neighbors=3)
    assert names == ["0", "2"]
    assert connectivity[0, 1] == pytest.approx(0.0)


def test_paga_step_labels_axes(tmp_path):
    values = [[0.0, 0.0], [0.1, 0.0], [10.0, 10.0], [10.1, 10.0]]
    ctx, exported = _run(
        PagaConnectivityStep(),
        {"n_neighbors": 2, "output": "paga"},
        [_embedding(values), _cluster_labels([3, 3, 7, 7])],
        tmp_path,
    )
    result = ctx["paga"]
    assert result.dims == ["cluster", "cluster_b"]
    assert list(result.labels["cluster"]) == ["3", "7"]
    assert result.data[0, 1] > 0.0
    assert exported["n_clusters"] == 2


def test_gene_trends_exact_bin_means():
    trends = gene_trends(
        np.array([[1.0, 10.0], [3.0, 30.0], [5.0, 50.0], [7.0, 70.0]]),
        np.array([0.05, 0.15, 0.55, 0.95]),
        n_bins=2,
    )
    assert trends.shape == (2, 2)
    assert trends[:, 0] == pytest.approx([2.0, 20.0])
    assert trends[:, 1] == pytest.approx([6.0, 60.0])


def test_gene_trends_empty_bin_is_nan():
    trends = gene_trends(
        np.array([[1.0], [2.0], [3.0]]),
        np.array([0.05, 0.05, 0.05]),
        n_bins=3,
    )
    assert trends[0, 0] == pytest.approx(2.0)
    assert np.isnan(trends[0, 1]) and np.isnan(trends[0, 2])


def test_gene_trends_step_labels(tmp_path):
    cells = ["a", "b", "c", "d"]
    ctx, exported = _run(
        TrajectoryGeneTrendsStep(),
        {"n_bins": 2, "output": "trends"},
        [
            _expression([[1.0, 10.0], [3.0, 30.0], [5.0, 50.0], [7.0, 70.0]], ["g1", "g2"], cells),
            _pseudotime([0.05, 0.15, 0.55, 0.95], cells),
        ],
        tmp_path,
    )
    result = ctx["trends"]
    assert result.dims == ["gene", "bin"]
    assert list(result.labels["bin"]) == ["0", "1"]
    assert result.data[1, 0] == pytest.approx(20.0)
    assert exported["n_occupied_bins"] == 2


def _write_pairs(tmp_path, rows):
    path = tmp_path / "pairs.csv"
    path.write_text("ligand,receptor\n" + "\n".join(f"{a},{b}" for a, b in rows) + "\n", encoding="utf-8")
    return str(path)


def test_cell_communication_scores_exact(tmp_path):
    cells = [f"c{index}" for index in range(8)]
    values = [[2.0, 0.0, 1.0]] * 4 + [[0.0, 3.0, 1.0]] * 4
    pairs = _write_pairs(tmp_path, [("L", "R"), ("L", "MISSING")])
    ctx, exported = _run(
        CellCommunicationStep(),
        {"pairs_table": pairs, "min_mean": 0.1, "output": "communication_scores"},
        [_expression(values, ["L", "R", "X"], cells), _cluster_labels([1, 1, 1, 1, 2, 2, 2, 2], cells)],
        tmp_path,
    )
    result = ctx["communication_scores"]
    assert result.dims == ["interaction", "score"]
    assert list(result.labels["interaction"]) == ["L^R|1|2"]
    assert result.data[0, 0] == pytest.approx(6.0)
    assert exported["n_pairs_usable"] == 1
    assert exported["n_pairs_skipped"] == 1


def test_cell_communication_min_mean_filters_sender(tmp_path):
    cells = [f"c{index}" for index in range(4)]
    values = [[0.05, 3.0]] * 2 + [[3.0, 0.0]] * 2
    pairs = _write_pairs(tmp_path, [("L", "R")])
    ctx, _ = _run(
        CellCommunicationStep(),
        {"pairs_table": pairs, "min_mean": 5.0, "output": "communication_scores"},
        [_expression(values, ["L", "R"], cells), _cluster_labels([1, 1, 2, 2], cells)],
        tmp_path,
    )
    result = ctx["communication_scores"]
    assert result.data.shape == (0, 1)
    assert result.labels["interaction"] == {}


def test_read_pairs_missing_file(tmp_path):
    with pytest.raises(ValueError, match="pairs table not found"):
        read_pairs(tmp_path / "absent.csv")


def test_read_pairs_accepts_headerless_table(tmp_path):
    path = tmp_path / "pairs.csv"
    path.write_text("CXCL8,CXCR1\nCCL5,CCR1\n", encoding="utf-8")
    assert read_pairs(path) == [("CXCL8", "CXCR1"), ("CCL5", "CCR1")]
