"""Standalone verification of the single-cell QC + clustering route.

Run with: python tasks/single_cell_route_demo/test_single_cell_route.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core import Form, StepError
from src.reader import read_source
from src.task.step.steps.qc_metrics import QcMetricsStep
from src.task.step.steps.filter_by import FilterByStep
from src.task.step.steps.filter_min import FilterMinStep
from src.task.step.steps.normalize import NormalizeStep
from src.task.step.steps.log_transform import LogTransformStep
from src.task.step.steps.rank_axis import RankAxisStep
from src.task.step.steps.reduce import ReduceStep
from src.task.step.steps.cluster_axis import ClusterAxisStep
from biopipe_sdk.testing import run_operator


DATA = (
    Path(__file__).parent
    / "input"
    / "filtered_gene_bc_matrices"
    / "hg19"
    / "matrix.mtx"
)


def _make_form(data, gene_labels, cell_labels):
    return Form(
        data=data.astype(np.float32),
        dims=["gene", "cell"],
        labels={
            "gene": {g: i for i, g in enumerate(gene_labels)},
            "cell": {c: i for i, c in enumerate(cell_labels)},
        },
        info={"missing_code": np.nan},
    )


def _load_real():
    if not DATA.exists():
        raise SystemExit(
            f"missing {DATA}; run tasks/single_cell_route_demo/download.sh first"
        )
    return read_source(
        DATA,
        dims=["gene", "cell"],
        labels={"gene": "builtin", "cell": "builtin"},
    )


def _preprocess_to_pcs(form):
    """QC -> filter cells -> filter genes -> normalize(total) -> log(e)
    -> HVG -> PCA. Matches the route's task.yaml."""
    qc = run_operator(QcMetricsStep, [form], {
        "feature_dim": "gene",
        "sample_dim": "cell",
        "metrics": [
            {"name": "total", "op": "sum"},
            {"name": "n_detected", "op": "nonzero"},
        ],
    })
    form = run_operator(FilterByStep, [form, qc], {
        "dim": "cell",
        "rules": [
            {"field": "total", "min": 500},
            {"field": "n_detected", "min": 200},
        ],
    })
    form = run_operator(FilterMinStep, [form], {
        "dim": "gene", "min_value": 1, "min_samples": 3,
    })
    form = run_operator(NormalizeStep, [form], {
        "method": "total", "dim": "cell",
    })
    form = run_operator(LogTransformStep, [form], {
        "base": "e", "pseudocount": 1,
    })
    hvg = run_operator(RankAxisStep, [form], {
        "dim": "gene", "by": "variance", "top_n": 2000,
    })
    pcs = run_operator(ReduceStep, [hvg], {
        "dim": "gene", "method": "pca", "n_components": 50,
    })
    return pcs


def test_qc_hand_counted():
    mat = np.array([
        [1, 0, 2, 0],
        [0, 3, 0, 1],
        [2, 1, 0, 0],
    ], dtype=np.float32)
    form = _make_form(mat, ["g0", "g1", "g2"], ["c0", "c1", "c2", "c3"])
    out = run_operator(QcMetricsStep, [form], {
        "feature_dim": "gene",
        "sample_dim": "cell",
        "metrics": [
            {"name": "total", "op": "sum"},
            {"name": "n_detected", "op": "nonzero"},
        ],
    })
    stat_labels = out.labels[out.dims[1]]
    cell_dim = [d for d in out.dims if d != out.dims[1]][0]
    cells = out.labels[cell_dim]
    total_idx = stat_labels["total"]
    nd_idx = stat_labels["n_detected"]
    assert float(out.data[cells["c0"], total_idx]) == 3.0
    assert float(out.data[cells["c1"], total_idx]) == 4.0
    assert float(out.data[cells["c2"], total_idx]) == 2.0
    assert float(out.data[cells["c3"], total_idx]) == 1.0
    assert float(out.data[cells["c0"], nd_idx]) == 2.0
    assert float(out.data[cells["c1"], nd_idx]) == 2.0
    assert float(out.data[cells["c2"], nd_idx]) == 1.0
    assert float(out.data[cells["c3"], nd_idx]) == 1.0
    print("  qc_metrics hand-counted              ok")


def test_filter_by_hand_counted():
    mat = np.array([
        [1, 0, 2, 0],
        [0, 3, 0, 1],
        [2, 1, 0, 0],
    ], dtype=np.float32)
    form = _make_form(mat, ["g0", "g1", "g2"], ["c0", "c1", "c2", "c3"])
    qc = run_operator(QcMetricsStep, [form], {
        "feature_dim": "gene",
        "sample_dim": "cell",
        "metrics": [
            {"name": "total", "op": "sum"},
            {"name": "n_detected", "op": "nonzero"},
        ],
    })
    out = run_operator(FilterByStep, [form, qc], {
        "dim": "cell",
        "rules": [
            {"field": "total", "min": 2},
            {"field": "n_detected", "min": 1},
        ],
    })
    kept = set(out.labels["cell"])
    assert "c0" in kept
    assert "c1" in kept
    assert "c2" in kept
    assert "c3" not in kept
    print("  filter_by hand-counted               ok")


def test_normalize_log_invariants():
    """total normalize: every cell sums to 1.0. ln(x+1) is exact."""
    form = _load_real()
    qc = run_operator(QcMetricsStep, [form], {
        "feature_dim": "gene", "sample_dim": "cell",
        "metrics": [
            {"name": "total", "op": "sum"},
            {"name": "n_detected", "op": "nonzero"},
        ],
    })
    form = run_operator(FilterByStep, [form, qc], {
        "dim": "cell",
        "rules": [
            {"field": "total", "min": 500},
            {"field": "n_detected", "min": 200},
        ],
    })
    normalized = run_operator(NormalizeStep, [form], {
        "method": "total", "dim": "cell",
    })
    per_cell = normalized.data.sum(axis=0)
    assert np.allclose(per_cell, 1.0, rtol=1e-4), per_cell[:5]
    logged = run_operator(LogTransformStep, [normalized], {
        "base": "e", "pseudocount": 1,
    })
    expected = np.log(normalized.data.astype(np.float64) + 1.0)
    assert np.allclose(logged.data, expected, rtol=1e-5, atol=1e-6)
    print("  normalize(total) + ln invariants     ok")


def test_hvg_and_pca_shapes():
    form = _load_real()
    qc = run_operator(QcMetricsStep, [form], {
        "feature_dim": "gene", "sample_dim": "cell",
        "metrics": [
            {"name": "total", "op": "sum"},
            {"name": "n_detected", "op": "nonzero"},
        ],
    })
    form = run_operator(FilterByStep, [form, qc], {
        "dim": "cell",
        "rules": [
            {"field": "total", "min": 500},
            {"field": "n_detected", "min": 200},
        ],
    })
    form = run_operator(FilterMinStep, [form], {
        "dim": "gene", "min_value": 1, "min_samples": 3,
    })
    form = run_operator(NormalizeStep, [form], {"method": "total", "dim": "cell"})
    form = run_operator(LogTransformStep, [form], {"base": "e", "pseudocount": 1})
    hvg = run_operator(RankAxisStep, [form], {
        "dim": "gene", "by": "variance", "top_n": 2000,
    })
    assert hvg.data.shape[0] == 2000
    pcs = run_operator(ReduceStep, [hvg], {
        "dim": "gene", "method": "pca", "n_components": 50,
    })
    assert pcs.dims == ["cell", "component"]
    assert pcs.data.shape[1] == 50
    var_per_comp = pcs.data.var(axis=0)
    assert np.all(np.diff(var_per_comp) <= 1e-6), var_per_comp[:5]
    print("  hvg top-2000 + PCA 50 components     ok")


def test_cluster_output():
    form = _load_real()
    pcs = _preprocess_to_pcs(form)
    clusters = run_operator(ClusterAxisStep, [pcs], {
        "dim": "cell",
        "method": "louvain",
        "n_neighbors": 10,
        "resolution": 2.0,
        "random_state": 0,
    })
    n_clusters = len(set(int(v) for v in clusters.data[:, 0]))
    assert n_clusters >= 2, f"expected >=2 clusters, got {n_clusters}"
    print(f"  louvain produced {n_clusters} clusters         ok")


def test_wrong_dim_rejected():
    form = _load_real()
    try:
        run_operator(QcMetricsStep, [form], {
            "feature_dim": "nonexistent",
            "sample_dim": "cell",
            "metrics": [{"name": "total", "op": "sum"}],
        })
        raise AssertionError("expected rejection")
    except AssertionError:
        raise
    except StepError:
        pass
    print("  wrong feature_dim rejected           ok")


def main():
    print("single_cell route verification")
    test_qc_hand_counted()
    test_filter_by_hand_counted()
    test_normalize_log_invariants()
    test_hvg_and_pca_shapes()
    test_cluster_output()
    test_wrong_dim_rejected()
    print()
    print("all checks passed")


if __name__ == "__main__":
    main()
