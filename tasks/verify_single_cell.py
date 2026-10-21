"""Independent verification of the single-cell route.

Compares operator output against independent NumPy implementations on
the same matrix, and against the 10x Genomics published summary
statistics for PBMC 3k (2,700 cells; median 819 genes per cell;
median 2,197 UMI counts per cell).

PCA is fed the HVG matrix directly. The route does not apply
scale_features before PCA: PCA's own standardize=True is the only
scaling step. An earlier version of this script stacked both and
collapsed Louvain to a single community on this dataset.

Run with: python tasks/verify_single_cell.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")

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


checks = []


def record(name, ok, expected, actual):
    checks.append((name, bool(ok), str(expected)[:50], str(actual)[:50]))


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def main():
    data = Path(
        "tasks/single_cell_route_demo/input/"
        "filtered_gene_bc_matrices/hg19/matrix.mtx"
    )
    if not data.exists():
        print(f"missing {data}; run tasks/single_cell_route_demo/download.sh first")
        sys.exit(1)

    section("1. Load and inspect")
    form = read_source(
        data,
        dims=["gene", "cell"],
        labels={"gene": "builtin", "cell": "builtin"},
    )
    n_genes, n_cells = form.data.shape
    record("gene count == 32738", n_genes == 32738, 32738, n_genes)
    record("cell count == 2700", n_cells == 2700, 2700, n_cells)

    section("2. QC metrics vs independent NumPy")
    qc = run_operator(QcMetricsStep, [form], {
        "feature_dim": "gene", "sample_dim": "cell",
        "metrics": [
            {"name": "total", "op": "sum"},
            {"name": "n_detected", "op": "nonzero"},
        ],
    })
    stat_labels = qc.labels[qc.dims[1]]
    cell_dim = [d for d in qc.dims if d != qc.dims[1]][0]
    cells = qc.labels[cell_dim]
    total_col = stat_labels["total"]
    nd_col = stat_labels["n_detected"]

    indep_total = form.data.sum(axis=0)
    indep_nd = (form.data > 0).sum(axis=0)

    max_total_err = 0.0
    max_nd_err = 0.0
    for lbl, i in cells.items():
        max_total_err = max(
            max_total_err,
            abs(float(qc.data[i, total_col]) - float(indep_total[i])),
        )
        max_nd_err = max(
            max_nd_err,
            abs(float(qc.data[i, nd_col]) - float(indep_nd[i])),
        )

    record("per-cell total matches independent",
            max_total_err < 1e-3, "max err < 1e-3", f"{max_total_err:.6f}")
    record("per-cell n_detected matches independent",
            max_nd_err < 1e-3, "max err < 1e-3", f"{max_nd_err:.6f}")

    median_total = float(np.median(indep_total))
    record("median total in [2000, 2400] (10x ~2197)",
            2000 <= median_total <= 2400, "2000..2400",
            f"{median_total:.0f}")

    median_nd = float(np.median(indep_nd))
    record("median n_detected in [750, 900] (10x ~819)",
            750 <= median_nd <= 900, "750..900", f"{median_nd:.0f}")

    section("3. Filter chain reduces cells and genes")
    cells_kept = run_operator(FilterByStep, [form, qc], {
        "dim": "cell",
        "rules": [
            {"field": "total", "min": 500},
            {"field": "n_detected", "min": 200},
        ],
    })
    n_cells_after = cells_kept.data.shape[1]
    record("cell filter keeps between 2000 and 2700",
            2000 <= n_cells_after <= 2700, "2000..2700", n_cells_after)

    genes_kept = run_operator(FilterMinStep, [cells_kept], {
        "dim": "gene", "min_value": 1, "min_samples": 3,
    })
    n_genes_after = genes_kept.data.shape[0]
    record("gene filter keeps between 10000 and 20000",
            10000 <= n_genes_after <= 20000, "10000..20000",
            n_genes_after)

    section("4. Normalize and log invariants")
    normalized = run_operator(NormalizeStep, [genes_kept], {
        "method": "total", "dim": "cell",
    })
    per_cell_sum = normalized.data.sum(axis=0)
    record("total normalize: every cell sums to 1",
            np.allclose(per_cell_sum, 1.0, rtol=1e-4),
            "all == 1",
            f"min={per_cell_sum.min():.2f} max={per_cell_sum.max():.2f}")

    logged = run_operator(LogTransformStep, [normalized], {
        "base": "e", "pseudocount": 1,
    })
    expected = np.log(normalized.data.astype(np.float64) + 1.0)
    record("ln(x+1) matches independent",
            np.allclose(logged.data, expected, rtol=1e-5, atol=1e-5),
            "allclose",
            "match" if np.allclose(logged.data, expected) else "mismatch")

    section("5. HVG, PCA, cluster")
    hvg = run_operator(RankAxisStep, [logged], {
        "dim": "gene", "by": "variance", "top_n": 2000,
    })
    record("HVG returns top 2000 genes", hvg.data.shape[0] == 2000,
            2000, hvg.data.shape[0])

    var_per_gene = logged.data.var(axis=1)
    kept_idx = [logged.labels["gene"][lbl] for lbl in hvg.labels["gene"]]
    removed_idx = [
        i for i in range(logged.data.shape[0]) if i not in set(kept_idx)
    ]
    if removed_idx:
        min_kept_var = min(var_per_gene[i] for i in kept_idx)
        max_removed_var = max(var_per_gene[i] for i in removed_idx)
        record("HVG: min kept variance >= max removed variance",
                min_kept_var >= max_removed_var - 1e-6,
                "kept >= removed",
                f"{min_kept_var:.4f} vs {max_removed_var:.4f}")

    pcs = run_operator(ReduceStep, [hvg], {
        "dim": "gene", "method": "pca", "n_components": 50,
    })
    record("PCA returns 50 components", pcs.data.shape[1] == 50,
            50, pcs.data.shape[1])
    var_per_comp = pcs.data.var(axis=0)
    record("PCA component variances non-increasing",
            bool(np.all(np.diff(var_per_comp) <= 1e-6)),
            "non-increasing", f"first 3 = {var_per_comp[:3].tolist()}")

    clusters = run_operator(ClusterAxisStep, [pcs], {
        "dim": "cell",
        "method": "louvain",
        "n_neighbors": 10,
        "resolution": 2.0,
        "random_state": 0,
    })
    n_clusters = len(set(int(v) for v in clusters.data[:, 0]))
    record("louvain produces at least 2 clusters", n_clusters >= 2,
            ">=2", n_clusters)

    print()
    print("=" * 78)
    print("Verification summary")
    print("=" * 78)
    print(f"{'':<4}{'check':<52}{'expected':>14}{'actual':>18}")
    print("-" * 78)
    for name, ok, exp, act in checks:
        status = "PASS" if ok else "FAIL"
        print(f"{status}  {name:<52}{exp:>14}{act:>18}")
    print("-" * 78)
    passed = sum(1 for _, ok, _, _ in checks if ok)
    print(f"{passed}/{len(checks)} checks passed")
    if passed < len(checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
