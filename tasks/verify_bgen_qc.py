"""Independent-implementation verification of the BGEN dosage QC route.

Every value computed by the operators is compared against a NumPy
implementation on the same dosage matrix, or against a mathematical
invariant of the operator.

Run with: python tasks/verify_bgen_qc.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")

from src.core import ReaderError
from src.reader import read_source
from src.task.step.steps.missing import MissingStep
from src.task.step.steps.maf import MafStep
from src.task.step.steps.ld_prune import LdPruneStep
from src.task.step.steps.pca import PcaStep
from biopipe_sdk.testing import run_operator


checks = []


def record(name, ok, expected, actual):
    checks.append((name, bool(ok), str(expected)[:40], str(actual)[:40]))


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def main():
    bgen = Path("tasks/bgen_qc_demo/input/example.bgen")
    hap = Path("tasks/bgen_demo/input/haplotypes.bgen")
    cplx = Path("tasks/bgen_demo/input/complex.bgen")
    if not bgen.exists():
        print(f"missing {bgen}")
        sys.exit(1)

    section("1. Reader: dosage range and metadata")
    form = read_source(
        bgen, dims=["variant", "sample"],
        labels={"variant": "builtin", "sample": "builtin"},
    )
    finite = form.data[np.isfinite(form.data)]
    record("shape == (199, 500)", form.data.shape == (199, 500), "(199,500)", form.data.shape)
    record("representation == dosage",
            form.info.get("representation") == "dosage",
            "dosage", form.info.get("representation"))
    record("ploidy == 2", form.info.get("ploidy") == 2, 2, form.info.get("ploidy"))
    record("dosage min >= 0", float(finite.min()) >= 0.0, ">= 0", f"{float(finite.min()):.4f}")
    record("dosage max <= 2", float(finite.max()) <= 2.0, "<= 2", f"{float(finite.max()):.4f}")

    section("2. Independent MAF vs MafStep kept set")
    dosage = form.data.astype(np.float64)
    n_valid = (~np.isnan(dosage)).sum(axis=1)
    alt_sum = np.nansum(dosage, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        alt_freq = alt_sum / (2.0 * n_valid)
    maf = np.minimum(alt_freq, 1.0 - alt_freq)

    out_maf = run_operator(MafStep, [form], {"dim": "variant", "threshold": 0.01})
    kept_idx = [form.labels["variant"][lbl] for lbl in out_maf.labels["variant"]]
    n_before = form.data.shape[0]
    n_kept = len(kept_idx)
    min_kept = min(maf[i] for i in kept_idx)
    record(f"kept {n_kept}/{n_before} variants have independent MAF >= 0.01",
            all(maf[i] >= 0.01 - 1e-6 for i in kept_idx),
            "all >= 0.01", f"min={min_kept:.4f}")
    removed_idx = [i for i in range(n_before) if i not in set(kept_idx)]
    if removed_idx:
        removed_maf = [maf[i] for i in removed_idx if np.isfinite(maf[i])]
        max_removed = max(removed_maf, default=0.0)
        record(f"removed {len(removed_idx)} variants have independent MAF < 0.01 or NaN",
                all((not np.isfinite(maf[i])) or maf[i] < 0.01 + 1e-6 for i in removed_idx),
                "all < 0.01", f"max={max_removed:.4f}")

    section("3. Independent missing rate vs MissingStep")
    miss_rate = np.isnan(dosage).mean(axis=1)
    out_sm = run_operator(MissingStep, [form], {"dim": "sample", "threshold": 0.10})
    out_vm = run_operator(MissingStep, [out_sm], {"dim": "variant", "threshold": 0.05})
    kept_v_idx = [out_sm.labels["variant"][lbl] for lbl in out_vm.labels["variant"]]
    max_miss = max(miss_rate[i] for i in kept_v_idx) if kept_v_idx else 0.0
    record(f"variant-kept {len(kept_v_idx)}/{out_sm.data.shape[0]} have independent missing rate <= 0.05",
            all(miss_rate[i] <= 0.05 + 1e-6 for i in kept_v_idx),
            "all <= 0.05", f"max={max_miss:.4f}")

    section("4. LD prune invariant: kept <= before and non-empty")
    out_pruned = run_operator(LdPruneStep, [out_vm], {"dim": "variant", "window": 50, "r2": 0.2})
    record("kept <= before",
            out_pruned.data.shape[0] <= out_vm.data.shape[0],
            f"<={out_vm.data.shape[0]}", out_pruned.data.shape[0])
    record("kept > 0", out_pruned.data.shape[0] > 0, "> 0", out_pruned.data.shape[0])

    section("5. PCA: component variances are non-increasing")
    out_pca = run_operator(PcaStep, [out_pruned], {"dim": "variant", "n_components": 5})
    scores = out_pca.data
    var_per_component = np.var(scores, axis=0)
    ratio = var_per_component / var_per_component.sum()
    record("component variance non-increasing",
            bool(np.all(np.diff(var_per_component) <= 1e-10)),
            "non-increasing", f"first 3 = {ratio[:3].tolist()}")
    record("PC1 variance > PCn variance",
            var_per_component[0] > var_per_component[-1],
            "PC1 > PCn", f"{var_per_component[0]:.4f} vs {var_per_component[-1]:.4f}")
    record("component variance ratios in (0, 1]",
            bool((ratio > 0).all() and (ratio <= 1.0 + 1e-6).all()),
            "in (0,1]", f"first = {ratio[0]:.4f}")

    section("6. Negative cases")
    if hap.exists():
        try:
            read_source(hap, dims=["variant", "sample"],
                        labels={"variant": "builtin", "sample": "builtin"})
            record("haplotypes.bgen rejected", False, "ReaderError", "no error")
        except ReaderError:
            record("haplotypes.bgen rejected (non-biallelic-diploid)", True, "ReaderError", "ReaderError")
        except Exception as exc:
            record("haplotypes.bgen rejected", False, "ReaderError", type(exc).__name__)
    if cplx.exists():
        try:
            read_source(cplx, dims=["variant", "sample"],
                        labels={"variant": "builtin", "sample": "builtin"})
            record("complex.bgen rejected", False, "ReaderError", "no error")
        except ReaderError:
            record("complex.bgen rejected (allow_complex path)", True, "ReaderError", "ReaderError")
        except Exception as exc:
            record("complex.bgen rejected", False, "ReaderError", type(exc).__name__)

    print()
    print("=" * 78)
    print("Verification summary")
    print("=" * 78)
    print(f"{'':<4}{'check':<56}{'expected':>12}{'actual':>14}")
    print("-" * 78)
    for name, ok, exp, act in checks:
        status = "PASS" if ok else "FAIL"
        print(f"{status}  {name:<56}{exp:>12}{act:>14}")
    print("-" * 78)
    passed = sum(1 for _, ok, _, _ in checks if ok)
    print(f"{passed}/{len(checks)} checks passed")
    if passed < len(checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
