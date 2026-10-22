"""Independent verification of the multi-omics route.

Run with: python tasks/verify_multi_omics.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")

from src.core import ReaderError, StepError
from src.reader import read_source
from src.task.step.steps.normalize import NormalizeStep
from src.task.step.steps.log_transform import LogTransformStep
from src.task.step.steps.pca import PcaStep
from src.task.step.steps.join import JoinStep
from biopipe_sdk.testing import run_operator


checks = []


def record(name, ok, expected, actual):
    checks.append((name, bool(ok), str(expected)[:40], str(actual)[:40]))


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def _read_h5_sums(path):
    """Read the h5 directly and sum per feature type."""
    import h5py
    from scipy.sparse import csc_matrix
    with h5py.File(path, "r") as f:
        m = f["matrix"]
        shape = tuple(int(x) for x in m["shape"][:])
        data = m["data"][:]
        indices = m["indices"][:]
        indptr = m["indptr"][:]
        ftypes = [
            s.decode() if isinstance(s, bytes) else str(s)
            for s in m["features"]["feature_type"][:]
        ]
        barcodes = [
            s.decode() if isinstance(s, bytes) else str(s)
            for s in m["barcodes"][:]
        ]
    mat = csc_matrix((data, indices, indptr), shape=shape).toarray()
    rna_mask = np.array([t == "Gene Expression" for t in ftypes])
    prot_mask = np.array([t == "Antibody Capture" for t in ftypes])
    return {
        "rna_rows": int(rna_mask.sum()),
        "protein_rows": int(prot_mask.sum()),
        "rna_sum": float(mat[rna_mask, :].sum()),
        "protein_sum": float(mat[prot_mask, :].sum()),
        "n_cells": len(barcodes),
        "n_features": len(ftypes),
    }


def main():
    data = Path("tasks/multi_omics_route_demo/input/cite_seq_pbmc.h5")
    if not data.exists():
        print(f"missing {data}")
        sys.exit(1)

    section("1. Reader against raw h5")
    indep = _read_h5_sums(data)
    rna = read_source(data, dims=["gene", "cell"],
                      labels={"gene": "builtin", "cell": "builtin"},
                      feature_type="Gene Expression")
    prot = read_source(data, dims=["protein", "cell"],
                       labels={"protein": "builtin", "cell": "builtin"},
                       feature_type="Antibody Capture")
    record("RNA feature count matches h5",
            rna.data.shape[0] == indep["rna_rows"],
            indep["rna_rows"], rna.data.shape[0])
    record("protein feature count matches h5",
            prot.data.shape[0] == indep["protein_rows"],
            indep["protein_rows"], prot.data.shape[0])
    record("RNA total count matches h5",
            abs(float(rna.data.sum()) - indep["rna_sum"]) < 1.0,
            f"{indep['rna_sum']:.0f}", f"{float(rna.data.sum()):.0f}")
    record("protein total count matches h5",
            abs(float(prot.data.sum()) - indep["protein_sum"]) < 1.0,
            f"{indep['protein_sum']:.0f}", f"{float(prot.data.sum()):.0f}")
    record("both share the same cell axis (5247)",
            (rna.data.shape[1] == prot.data.shape[1] == 5247),
            5247, rna.data.shape[1])

    section("2. Normalize / log invariants")
    prot_norm = run_operator(NormalizeStep, [prot], {"method": "total", "dim": "cell"})
    per_cell = prot_norm.data.sum(axis=0)
    record("protein total-normalize: every cell sum == 1",
            np.allclose(per_cell, 1.0, rtol=1e-4),
            "all == 1", f"min={per_cell.min():.4f} max={per_cell.max():.4f}")
    prot_log = run_operator(LogTransformStep, [prot_norm],
                            {"base": 2, "pseudocount": 1})
    expected = np.log2(prot_norm.data.astype(np.float64) + 1.0)
    record("protein log2(x+1) matches independent",
            np.allclose(prot_log.data, expected, rtol=1e-5, atol=1e-6),
            "allclose", "match")

    section("3. PCA on protein and RNA")
    prot_pcs = run_operator(PcaStep, [prot_log],
                            {"dim": "protein", "n_components": 20})
    record("protein PCA returns 20 components",
            prot_pcs.data.shape[1] == 20, 20, prot_pcs.data.shape[1])
    v = prot_pcs.data.var(axis=0)
    record("protein PCA component variances non-increasing",
            bool(np.all(np.diff(v) <= 1e-6)),
            "non-increasing", f"first 3 = {v[:3].tolist()}")

    rna_norm = run_operator(NormalizeStep, [rna], {"method": "cpm", "dim": "cell", "target_sum": 1e6})
    rna_log = run_operator(LogTransformStep, [rna_norm], {"base": 2, "pseudocount": 1})
    from src.task.step.steps.rank_axis import RankAxisStep
    rna_hvg = run_operator(RankAxisStep, [rna_log], {"dim": "gene", "by": "variance", "top_n": 2000})
    record("RNA HVG top 2000 genes", rna_hvg.data.shape[0] == 2000,
            2000, rna_hvg.data.shape[0])
    rna_pcs = run_operator(PcaStep, [rna_hvg],
                           {"dim": "gene", "n_components": 20})
    record("RNA PCA returns 20 components", rna_pcs.data.shape[1] == 20,
            20, rna_pcs.data.shape[1])

    section("4. Join by cell")
    joined = run_operator(JoinStep, [rna_pcs, prot_pcs], {
        "dim": "cell", "columns": "all", "how": "inner", "prefix": "prot_",
    })
    record("joined cell count == 5247",
            joined.data.shape[0] == 5247, 5247, joined.data.shape[0])
    comp_labels = list(joined.labels["component"].keys())
    record("joined has both PC and prot_PC columns",
            any(l.startswith("PC") for l in comp_labels)
            and any(l.startswith("prot_PC") for l in comp_labels),
            "PC*/prot_PC*", f"{len(comp_labels)} labels")

    section("5. Negative case")
    try:
        read_source(data, dims=["gene", "cell"],
                    labels={"gene": "builtin", "cell": "builtin"},
                    feature_type="NoSuchType")
        record("unknown feature_type rejected", False, "StepError", "no error")
    except (StepError, ReaderError):
        record("unknown feature_type rejected", True, "ReaderError/StepError", "ReaderError/StepError")
    except Exception as exc:
        record("unknown feature_type rejected", False, "StepError", type(exc).__name__)

    print()
    print("=" * 78)
    print("Verification summary")
    print("=" * 78)
    print(f"{'':<4}{'check':<52}{'expected':>12}{'actual':>14}")
    print("-" * 78)
    for name, ok, exp, act in checks:
        status = "PASS" if ok else "FAIL"
        print(f"{status}  {name:<52}{exp:>12}{act:>14}")
    print("-" * 78)
    passed = sum(1 for _, ok, _, _ in checks if ok)
    print(f"{passed}/{len(checks)} checks passed")
    if passed < len(checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
