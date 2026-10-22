"""Standalone verification of the multi-omics route.

Run with: python tasks/multi_omics_route_demo/test_multi_omics_route.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core import Form, ReaderError, StepError
from src.reader import read_source
from src.task.step.steps.normalize import NormalizeStep
from src.task.step.steps.log_transform import LogTransformStep
from src.task.step.steps.pca import PcaStep
from src.task.step.steps.join import JoinStep
from biopipe_sdk.testing import run_operator


DATA = Path(__file__).parent / "input" / "cite_seq_pbmc.h5"


def _load_rna():
    if not DATA.exists():
        raise SystemExit(f"missing {DATA}")
    return read_source(
        DATA, dims=["gene", "cell"],
        labels={"gene": "builtin", "cell": "builtin"},
        feature_type="Gene Expression",
    )


def _load_protein():
    return read_source(
        DATA, dims=["protein", "cell"],
        labels={"protein": "builtin", "cell": "builtin"},
        feature_type="Antibody Capture",
    )


def test_reader_shapes():
    rna = _load_rna()
    prot = _load_protein()
    assert rna.data.shape[1] == 5247, rna.data.shape
    assert prot.data.shape[0] == 32, prot.data.shape
    assert set(rna.info["feature_types"]) == {"Gene Expression"}
    assert set(prot.info["feature_types"]) == {"Antibody Capture"}
    # Same barcode set on both axes.
    assert set(rna.labels["cell"].keys()) == set(prot.labels["cell"].keys())
    print("  reader RNA/protein shapes            ok")


def test_normalize_total_and_log():
    prot = _load_protein()
    norm = run_operator(NormalizeStep, [prot], {"method": "total", "dim": "cell"})
    per_cell = norm.data.sum(axis=0)
    assert np.allclose(per_cell, 1.0, rtol=1e-4), per_cell[:5]
    logged = run_operator(LogTransformStep, [norm], {"base": 2, "pseudocount": 1})
    expected = np.log2(norm.data.astype(np.float64) + 1.0)
    assert np.allclose(logged.data, expected, rtol=1e-5, atol=1e-6)
    print("  protein total-normalize + log2       ok")


def test_pca_dims():
    prot = _load_protein()
    norm = run_operator(NormalizeStep, [prot], {"method": "total", "dim": "cell"})
    logged = run_operator(LogTransformStep, [norm], {"base": 2, "pseudocount": 1})
    pcs = run_operator(PcaStep, [logged], {"dim": "protein", "n_components": 20})
    assert pcs.dims == ["cell", "component"]
    assert pcs.data.shape == (5247, 20)
    var = pcs.data.var(axis=0)
    assert np.all(np.diff(var) <= 1e-6), var[:5]
    print("  protein PCA 20 components            ok")


def test_join_alignment():
    prot = _load_protein()
    norm = run_operator(NormalizeStep, [prot], {"method": "total", "dim": "cell"})
    logged = run_operator(LogTransformStep, [norm], {"base": 2, "pseudocount": 1})
    pcs = run_operator(PcaStep, [logged], {"dim": "protein", "n_components": 5})
    # Join protein PCA onto itself to check dims and prefix.
    joined = run_operator(JoinStep, [pcs, pcs], {
        "dim": "cell", "columns": "all", "how": "inner",
        "prefix": "b_",
    })
    assert joined.dims == ["cell", "component"]
    assert joined.data.shape[0] == 5247
    comp_labels = joined.labels["component"]
    for i in range(5):
        assert f"PC{i+1}" in comp_labels
        assert f"b_PC{i+1}" in comp_labels
    print("  join alignment on cell axis          ok")


def test_wrong_feature_type_rejected():
    try:
        read_source(
            DATA, dims=["gene", "cell"],
            labels={"gene": "builtin", "cell": "builtin"},
            feature_type="NoSuchType",
        )
        raise AssertionError("expected rejection")
    except AssertionError:
        raise
    except (StepError, ReaderError) as exc:
        assert "no features with feature_type" in str(exc)
    print("  wrong feature_type rejected          ok")


def main():
    print("multi-omics route verification")
    test_reader_shapes()
    test_normalize_total_and_log()
    test_pca_dims()
    test_join_alignment()
    test_wrong_feature_type_rejected()
    print()
    print("all checks passed")


if __name__ == "__main__":
    main()
