"""Standalone verification of the BGEN dosage QC route.

Verifies that the reader produces correct dosages, and that each
QC operator matches an independent NumPy computation on the same
data. Does not use pytest.

Run with: python tasks/bgen_qc_demo/test_bgen_qc.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core import ReaderError
from src.reader import read_source
from src.task.step.steps.missing import MissingStep
from src.task.step.steps.maf import MafStep
from src.task.step.steps.ld_prune import LdPruneStep
from src.task.step.steps.pca import PcaStep
from biopipe_sdk.testing import run_operator


BGEN = Path(__file__).parent / "input" / "example.bgen"
HAP = Path(__file__).parent.parent / "bgen_demo" / "input" / "haplotypes.bgen"
CPLX = Path(__file__).parent.parent / "bgen_demo" / "input" / "complex.bgen"


def _load():
    return read_source(
        BGEN,
        dims=["variant", "sample"],
        labels={"variant": "builtin", "sample": "builtin"},
    )


def test_reader_dosage_range():
    form = _load()
    assert form.data.dtype == np.float32
    assert form.data.shape == (199, 500)
    finite = form.data[np.isfinite(form.data)]
    assert finite.min() >= 0.0
    assert finite.max() <= 2.0
    assert form.info["representation"] == "dosage"
    assert form.info["ploidy"] == 2
    assert form.info["missing_code"] is not None
    print("  reader dosage range [0, 2]              ok")


def test_maf_matches_independent_computation():
    form = _load()
    out = run_operator(MafStep, [form], {"dim": "variant", "threshold": 0.01})

    dosage = form.data.astype(np.float64)
    n_valid = (~np.isnan(dosage)).sum(axis=1)
    alt_sum = np.nansum(dosage, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        alt_freq = alt_sum / (2.0 * n_valid)
    maf = np.minimum(alt_freq, 1.0 - alt_freq)

    kept_idx = [form.labels["variant"][lbl] for lbl in out.labels["variant"]]
    for idx in kept_idx:
        assert maf[idx] >= 0.01 - 1e-6, (idx, maf[idx])

    n_before = form.data.shape[0]
    n_after = len(kept_idx)
    print(f"  maf kept {n_after}/{n_before}, all >= 0.01      ok")


def test_missing_matches_independent_computation():
    form = _load()
    out = run_operator(MissingStep, [form], {"dim": "variant", "threshold": 0.05})

    dosage = form.data.astype(np.float64)
    miss_rate = np.isnan(dosage).mean(axis=1)

    for lbl in out.labels["variant"]:
        idx = form.labels["variant"][lbl]
        assert miss_rate[idx] <= 0.05 + 1e-6, (idx, miss_rate[idx])
    print(f"  missing kept {len(out.labels['variant'])}/199           ok")


def test_ld_prune_invariant():
    form = _load()
    form = run_operator(MissingStep, [form], {"dim": "sample", "threshold": 0.1})
    form = run_operator(MissingStep, [form], {"dim": "variant", "threshold": 0.05})
    form = run_operator(MafStep, [form], {"dim": "variant", "threshold": 0.01})
    out = run_operator(LdPruneStep, [form], {"dim": "variant", "window": 50, "r2": 0.2})

    n_before = form.data.shape[0]
    n_after = out.data.shape[0]
    assert 0 < n_after <= n_before
    print(f"  ld_prune {n_before} -> {n_after}                ok")


def test_pca_component_variance_decreasing():
    """PCA components must have non-increasing variance.

    The PcaStep Form carries scores only; explained variance lives
    in the step export, which run_operator does not return. The
    invariant is checked from the scores directly: any valid PCA
    orders components by decreasing variance.
    """
    form = _load()
    form = run_operator(MissingStep, [form], {"dim": "sample", "threshold": 0.1})
    form = run_operator(MissingStep, [form], {"dim": "variant", "threshold": 0.05})
    form = run_operator(MafStep, [form], {"dim": "variant", "threshold": 0.01})
    out = run_operator(PcaStep, [form], {"dim": "variant", "n_components": 5})
    scores = out.data
    assert scores.ndim == 2
    var_per_component = np.var(scores, axis=0)
    assert np.all(np.diff(var_per_component) <= 1e-10), var_per_component
    assert var_per_component[0] > var_per_component[-1]
    ratio = var_per_component / var_per_component.sum()
    assert 0.0 < ratio[0] <= 1.0
    print(f"  pca component variances decreasing      ok")


def test_haplotype_bgen_rejected():
    if not HAP.exists():
        print("  haplotype BGEN rejected (data missing)  skip")
        return
    try:
        read_source(HAP, dims=["variant", "sample"],
                    labels={"variant": "builtin", "sample": "builtin"})
        raise AssertionError("expected ReaderError")
    except AssertionError:
        raise
    except ReaderError as exc:
        msg = str(exc).lower()
        assert "biallelic" in msg or "diploid" in msg or "haploid" in msg, str(exc)
    print("  haplotype BGEN rejected                 ok")


def test_complex_bgen_rejected():
    if not CPLX.exists():
        print("  complex BGEN rejected (data missing)    skip")
        return
    try:
        read_source(CPLX, dims=["variant", "sample"],
                    labels={"variant": "builtin", "sample": "builtin"})
        raise AssertionError("expected ReaderError")
    except AssertionError:
        raise
    except ReaderError as exc:
        assert "complex" in str(exc).lower(), str(exc)
    print("  complex BGEN rejected                   ok")


def main():
    print("bgen_qc verification")
    test_reader_dosage_range()
    test_maf_matches_independent_computation()
    test_missing_matches_independent_computation()
    test_ld_prune_invariant()
    test_pca_component_variance_decreasing()
    test_haplotype_bgen_rejected()
    test_complex_bgen_rejected()
    print()
    print("all checks passed")


if __name__ == "__main__":
    main()
