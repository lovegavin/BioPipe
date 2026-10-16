"""Verification of genetics operators against independent references.

Data: tasks/gwas_demo/input/{geno.vcf, phenotype.csv, covariates.csv}
      — the shipped GWAS demo inputs.

Run with: python tasks/verify_genetics_operators.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")

from scipy import stats

from src.core import Form
from src.reader import read_source
from biopipe_sdk.testing import run_operator

from src.task.step.steps.maf import MafStep
from src.task.step.steps.hwe import HweStep
from src.task.step.steps.ld_prune import LdPruneStep
from src.task.step.steps.regress import RegressStep


checks = []


def record(name, ok, expected, actual):
    checks.append((name, bool(ok), str(expected)[:52], str(actual)[:52]))


def section(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


# ---------------------------------------------------------------- data
geno = read_source(
    "tasks/gwas_demo/input/geno.vcf",
    ["variant", "sample"],
    {"variant": "builtin", "sample": "builtin"},
)
print(f"geno      : {geno.data.shape}, dims={geno.dims}")
print(f"ploidy    : {geno.info.get('ploidy')}")
print(f"rep       : {geno.info.get('representation')}")


# ---------------------------------------------------------------- 1
section("1. maf — reference: manual allele frequency from genotypes")

# reference: per variant, alt allele count / total alleles (non-missing)
G = geno.data.astype(np.float64)
# hard_call in {0, 1, 2}; missing is NaN
alt_count = np.nansum(G, axis=1)
valid_mask = np.isfinite(G)
allele_count = valid_mask.sum(axis=1) * 2
with np.errstate(invalid="ignore", divide="ignore"):
    p = alt_count / allele_count
ref_maf = np.minimum(p, 1.0 - p)

maf_out = run_operator(
    MafStep, [geno],
    {"dim": "variant", "threshold": 0.0, "output": "out"},
)
# MafStep with threshold 0 keeps everything; extract per-variant maf from
# the export, or better: run and inspect the dropped labels to infer
# the computed values. The operator does not expose per-variant maf, so
# verify by thresholding: run twice with a known cut and compare the
# kept set to the reference.
for thr in (0.05, 0.10, 0.20):
    out = run_operator(
        MafStep, [geno],
        {"dim": "variant", "threshold": thr, "output": "out"},
    )
    kept_labels = set(out.labels["variant"].keys())
    pos_to_label = {v: k for k, v in geno.labels["variant"].items()}
    ref_kept = {pos_to_label[i] for i in range(G.shape[0])
                if np.isfinite(ref_maf[i]) and ref_maf[i] >= thr}
    record(f"maf(threshold={thr}) kept set matches manual computation",
           kept_labels == ref_kept,
           f"{len(ref_kept)} kept", f"{len(kept_labels)} kept")


# ---------------------------------------------------------------- 2
section("2. hwe — reference: Wigginton et al. 2005 exact test")


def hwe_exact(obs_hets, obs_hom1, obs_hom2):
    """Exact HWE p-value, standard Wigginton 2005 formulation.

    het parity is fixed by the rare allele count (2*homc + het), not
    by the genotype count. Enumerating only states with the correct
    parity is essential; otherwise the observed state can be rejected
    as unreachable and yield spurious NaN.
    """
    genotypes = obs_hets + obs_hom1 + obs_hom2
    if genotypes == 0:
        return np.nan
    rare_copies = 2 * min(obs_hom1, obs_hom2) + obs_hets
    if rare_copies == 0:
        return 1.0

    from math import lgamma

    def log_fact(x):
        return lgamma(x + 1.0)

    def log_unnorm(het):
        homc = (rare_copies - het) // 2
        homr = genotypes - het - homc
        if het < 0 or homr < 0 or homc < 0:
            return -np.inf
        return (
            log_fact(genotypes) - log_fact(het)
            - log_fact(homr) - log_fact(homc)
            + het * np.log(2.0)
        )

    hets = list(range(rare_copies % 2, rare_copies + 1, 2))
    log_probs = np.array([log_unnorm(h) for h in hets], dtype=np.float64)
    if not np.isfinite(log_probs).any():
        return np.nan
    log_probs -= log_probs.max()
    probs = np.exp(log_probs)
    total = probs.sum()
    if total == 0:
        return np.nan
    probs /= total
    if obs_hets not in hets:
        return np.nan
    obs_idx = hets.index(obs_hets)
    cutoff = probs[obs_idx] * (1.0 + 1e-9)
    return float(min(1.0, probs[probs <= cutoff].sum()))


# For each variant with valid calls, count hom_ref / het / hom_alt
hwe_out = run_operator(
    HweStep, [geno],
    {"dim": "variant", "threshold": 0.0, "output": "out"},
)
pos_to_label = {v: k for k, v in geno.labels["variant"].items()}
kept_labels = set(hwe_out.labels["variant"].keys())

# recompute reference for threshold=0.0 (keep everything that passes)
ref_p = []
for i in range(G.shape[0]):
    row = G[i]
    row = row[np.isfinite(row)]
    h1 = int((row == 0).sum())
    h2 = int((row == 2).sum())
    he = int((row == 1).sum())
    if h1 + h2 + he == 0:
        ref_p.append(np.nan)
        continue
    ref_p.append(hwe_exact(he, h1, h2))
ref_p = np.asarray(ref_p)

# run with a meaningful threshold and compare kept sets
for thr in (0.0, 0.001, 0.01):
    out = run_operator(
        HweStep, [geno],
        {"dim": "variant", "threshold": thr, "output": "out"},
    )
    kept = set(out.labels["variant"].keys())
    ref_kept = {pos_to_label[i] for i in range(G.shape[0])
                if np.isfinite(ref_p[i]) and ref_p[i] >= thr}
    record(f"hwe(threshold={thr}) kept set matches Wigginton exact test",
           kept == ref_kept,
           f"{len(ref_kept)} kept", f"{len(kept)} kept")


# ---------------------------------------------------------------- 3
section("3. ld_prune — reference: r² from Pearson correlation")


def pairwise_r2(X, i, j):
    a = X[i]
    b = X[j]
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() < 2:
        return np.nan
    aa = a[m]
    bb = b[m]
    if aa.std() == 0 or bb.std() == 0:
        return np.nan
    r = np.corrcoef(aa, bb)[0, 1]
    return float(r * r)


# simple reference: greedy prune from left to right, drop variant j when
# some previously kept variant i within `window` has r² >= r2_thr
def ld_prune_ref(X, window, r2_thr):
    n = X.shape[0]
    kept = []
    for j in range(n):
        drop = False
        for i in kept:
            if j - i > window:
                continue
            r2 = pairwise_r2(X, i, j)
            if np.isfinite(r2) and r2 >= r2_thr:
                drop = True
                break
        if not drop:
            kept.append(j)
    return kept


for window, r2_thr in ((50, 0.2), (10, 0.5)):
    out = run_operator(
        LdPruneStep, [geno],
        {"dim": "variant", "window": window, "r2": r2_thr,
         "output": "out"},
    )
    kept = set(out.labels["variant"].keys())
    ref_kept_positions = ld_prune_ref(G, window, r2_thr)
    ref_kept = {pos_to_label[i] for i in ref_kept_positions}
    record(f"ld_prune(window={window}, r2={r2_thr}) kept set matches greedy ref",
           kept == ref_kept,
           f"{len(ref_kept)} kept", f"{len(kept)} kept")


# ---------------------------------------------------------------- 4
section("4. regress(ols) — reference: statsmodels.OLS")

pheno = read_source(
    "tasks/gwas_demo/input/phenotype.csv",
    ["sample", "feature"],
    {"sample": {"feature": 0}, "feature": "builtin"},
)
covar = read_source(
    "tasks/gwas_demo/input/covariates.csv",
    ["sample", "feature"],
    {"sample": {"feature": 0}, "feature": "builtin"},
)
print(f"pheno     : {pheno.data.shape}, feature labels = "
      f"{sorted(pheno.labels['feature'].items())}")
print(f"covar     : {covar.data.shape}, feature labels = "
      f"{sorted(covar.labels['feature'].items())}")

trait_col = pheno.labels["feature"]["trait_value"]
covar_a = covar.labels["feature"]["sex"]
covar_b = covar.labels["feature"]["batch"]
pheno_samples = [k for k, _ in sorted(
    pheno.labels["sample"].items(), key=lambda kv: kv[1])]
covar_samples = [k for k, _ in sorted(
    covar.labels["sample"].items(), key=lambda kv: kv[1])]
geno_samples = [k for k, _ in sorted(
    geno.labels["sample"].items(), key=lambda kv: kv[1])]
assert pheno_samples == covar_samples == geno_samples, \
    "sample order mismatch between files"

n_samples = len(pheno_samples)
trait = pheno.data[:, trait_col].astype(np.float64)
sex = covar.data[:, covar_a].astype(np.float64)
batch = covar.data[:, covar_b].astype(np.float64)

# Pick a non-constant variant so the regression has a real predictor.
G_all = geno.data.astype(np.float64)
finite_per_var = np.isfinite(G_all)
std_per_var = np.array([
    np.nanstd(G_all[i][finite_per_var[i]]) if finite_per_var[i].any() else 0.0
    for i in range(G_all.shape[0])
])
variant_row = int(np.argmax(std_per_var > 0))
print(f"chosen variant_row = {variant_row}, "
      f"std = {std_per_var[variant_row]:.4f}")
g = G_all[variant_row]

# Keep only samples with all values finite.
keep = (np.isfinite(trait) & np.isfinite(sex)
        & np.isfinite(batch) & np.isfinite(g))
trait_k = trait[keep]
sex_k = sex[keep]
batch_k = batch[keep]
g_k = g[keep]
print(f"kept {keep.sum()}/{n_samples} samples")

# Reference OLS: response = trait, predictors = [sex, batch, g], plus intercept.
D_ref = np.column_stack([np.ones(keep.sum()), sex_k, batch_k, g_k])
import statsmodels.api as sm
model = sm.OLS(trait_k, D_ref).fit()
ref_beta_g = float(model.params[3])
ref_se_g = float(model.bse[3])
ref_p_g = float(model.pvalues[3])

# Operator input: one feature row per variable; response="trait",
# covariates=["sex","batch"], remaining feature (g0) is the predictor.
combined_data = np.column_stack([trait_k, sex_k, batch_k, g_k]).T.astype(np.float32)
kept_samples = [s for s, k in zip(geno_samples, keep) if k]
combined = Form(
    data=combined_data,
    dims=["feature", "sample"],
    labels={
        "feature": {"trait": 0, "sex": 1, "batch": 2, "g0": 3},
        "sample": {s: i for i, s in enumerate(kept_samples)},
    },
    info={"missing_code": np.nan},
)
reg = run_operator(
    RegressStep, [combined],
    {"dim": "feature", "response": "trait",
     "covariates": ["sex", "batch"], "method": "ols", "output": "out"},
)
print(f"regress dims      : {reg.dims}")
print(f"regress labels    : {reg.labels['feature']}")
print(f"statistic labels  : {reg.labels['statistic']}")

beta_idx = reg.labels["statistic"]["BETA"]
se_idx = reg.labels["statistic"]["SE"]
p_idx = reg.labels["statistic"]["P"]
g_row = reg.labels["feature"]["g0"]

op_beta = float(reg.data[g_row, beta_idx])
op_se = float(reg.data[g_row, se_idx])
op_p = float(reg.data[g_row, p_idx])

record("regress(ols): beta for the genotype predictor matches statsmodels",
       abs(op_beta - ref_beta_g) < 1e-3 * max(1.0, abs(ref_beta_g)),
       f"{ref_beta_g:.6f}", f"{op_beta:.6f}")
record("regress(ols): SE matches statsmodels",
       abs(op_se - ref_se_g) < 1e-3 * max(1.0, abs(ref_se_g)),
       f"{ref_se_g:.6f}", f"{op_se:.6f}")
record("regress(ols): P matches statsmodels",
       abs(op_p - ref_p_g) < 1e-3 * max(1.0, abs(ref_p_g)),
       f"{ref_p_g:.6f}", f"{op_p:.6f}")


# ---------------------------------------------------------------- summary
print()
print("=" * 78)
print("Verification summary")
print("=" * 78)
n_pass = sum(1 for _, ok, _, _ in checks if ok)
print(f"{'':4s}{'check':<64s}{'expected':<20s}{'actual':<22s}")
print("-" * 78)
for name, ok, exp, act in checks:
    status = "PASS" if ok else "FAIL"
    print(f"{status:4s}  {name:<62s}  {exp:<18s}  {act:<20s}")
print("-" * 78)
print(f"{n_pass}/{len(checks)} checks passed")
