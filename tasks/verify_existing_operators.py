"""Verification of pre-v4 built-in operators against scipy/numpy baselines.

Every check uses real data and compares against an independent reference
computed with scipy, statsmodels, or numpy directly. No hand-crafted
expected numbers.

Run with: python tasks/verify_existing_operators.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")

from scipy import stats
from scipy.spatial import distance as scipy_distance

from src.core import Form
from src.reader import read_source
from biopipe_sdk.testing import run_operator

from src.task.step.steps.normalize import NormalizeStep
from src.task.step.steps.log_transform import LogTransformStep
from src.task.step.steps.impute import ImputeStep
from src.task.step.steps.compare_groups import CompareGroupsStep
from src.task.step.steps.correction import CorrectionStep
from src.task.step.steps.pca import PcaStep
from src.task.step.steps.reduce_axis import ReduceAxisStep
from src.task.step.steps.rank_axis import RankAxisStep
from src.task.step.steps.missing import MissingStep
from src.task.step.steps.filter_min import FilterMinStep
from src.task.step.steps.diversity import DiversityStep
from src.task.step.steps.distance_matrix import DistanceMatrixStep
from src.task.step.steps.correlation import CorrelationStep


checks = []


def record(name, ok, expected, actual):
    checks.append((name, bool(ok), str(expected)[:50], str(actual)[:50]))


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# ---------------------------------------------------------------- shared
airway = read_source(
    "tasks/rnaseq_de_demo/input/airway_counts.csv",
    ["gene", "sample"],
    {"gene": {"sample": 0}, "sample": "builtin"},
)
meta = read_source(
    "tasks/rnaseq_de_demo/input/airway_colData.csv",
    ["sample", "feature"],
    {"sample": {"feature": 0}, "feature": "builtin"},
)
print(f"airway counts : {airway.data.shape}, dims={airway.dims}")
print(f"airway meta   : {meta.data.shape}, dims={meta.dims}")
print(f"meta feature labels: {meta.labels['feature']}")


# ---------------------------------------------------------------- 1
section("1. normalize — mathematical invariants")

# CPM: each sample column sums to target_sum
cpm = run_operator(NormalizeStep, [airway],
                   {"method": "cpm", "dim": "sample",
                    "target_sum": 1e6})
col_sums = np.nansum(cpm.data, axis=0)
target_ok = np.allclose(col_sums, 1e6, rtol=1e-3)
record("normalize(cpm): each sample sum == 1e6",
       target_ok, "1e6", f"max dev {np.abs(col_sums - 1e6).max():.2f}")

# total: each sample sums to 1
total = run_operator(NormalizeStep, [airway],
                     {"method": "total", "dim": "sample"})
col_sums = np.nansum(total.data, axis=0)
record("normalize(total): each sample sum == 1",
       np.allclose(col_sums, 1.0, rtol=1e-3), "1.0",
       f"max dev {np.abs(col_sums - 1.0).max():.3e}")

# zscore: each sample mean ~0, std ~1
zs = run_operator(NormalizeStep, [airway],
                  {"method": "zscore", "dim": "sample"})
means = np.nanmean(zs.data, axis=0)
stds = np.nanstd(zs.data, axis=0)
record("normalize(zscore): sample mean == 0",
       np.allclose(means, 0.0, atol=1e-5), "0.0",
       f"max |mean| {np.abs(means).max():.2e}")
record("normalize(zscore): sample std == 1",
       np.allclose(stds, 1.0, atol=1e-3), "1.0",
       f"max |std-1| {np.abs(stds - 1).max():.2e}")

# quantile: after sort, all samples share the same ranked distribution
qt = run_operator(NormalizeStep, [airway],
                  {"method": "quantile", "dim": "sample"})
# Reference QN: for each sample column, sort its values; the k-th
# smallest value in every column becomes the mean of the k-th smallest
# values across columns. After the operator runs, sorting each column
# of its output must reproduce that target vector.
X = airway.data.astype(np.float64)
sorted_ref = np.sort(X, axis=0)
target = sorted_ref.mean(axis=1)
sorted_out = np.sort(qt.data.astype(np.float64), axis=0)
ref_broadcast = np.broadcast_to(target[:, None], sorted_out.shape)
max_dev = float(np.abs(sorted_out - ref_broadcast).max())
scale = float(np.abs(target).max())
rel_dev = max_dev / max(scale, 1.0)
record("normalize(quantile): sorted columns match target rank means",
       rel_dev < 1e-3, "<1e-3", f"{rel_dev:.2e}")

# median_of_ratios: verify size factors independently using DESeq2 definition
mor = run_operator(NormalizeStep, [airway],
                   {"method": "median_of_ratios", "dim": "sample"})
# DESeq2 reference: geometric mean per gene over samples that are all
# valid and strictly positive; size factor per sample is the median of
# count / geo_mean across eligible genes.
X = airway.data.astype(np.float64)     # (gene, sample)
valid = np.isfinite(X)
has_valid_zero = (valid & (X == 0)).any(axis=1)
eligible = valid.all(axis=1) & ~has_valid_zero
Xe = X[eligible]
log_geo = np.mean(np.log(Xe), axis=1)
geo = np.exp(log_geo)
ratios = Xe / geo[:, None]
ref_sf = np.median(ratios, axis=0)
raw_sums = np.sum(X, axis=0)
ref_colsum = raw_sums / ref_sf
actual_colsum = np.nansum(mor.data, axis=0)
rel_diff = float(np.abs(actual_colsum - ref_colsum).max() / ref_colsum.max())
record("normalize(median_of_ratios): column sums match DESeq2 reference",
       rel_diff < 1e-3, "DESeq2 sf formula", f"max rel diff {rel_diff:.2e}")


# ---------------------------------------------------------------- 2
section("2. log_transform — mathematical identity")

logged = run_operator(LogTransformStep, [airway],
                      {"base": 2, "pseudocount": 1})
expected = np.log2(airway.data + 1)
record("log_transform(base=2, pseudocount=1) matches np.log2(x+1)",
       np.allclose(logged.data, expected, atol=1e-6, equal_nan=True),
       "np.log2(x+1)", "match")

logged10 = run_operator(LogTransformStep, [airway],
                        {"base": 10, "pseudocount": 0.5})
expected10 = np.log10(airway.data + 0.5)
record("log_transform(base=10, pseudocount=0.5) matches np.log10(x+0.5)",
       np.allclose(logged10.data, expected10, atol=1e-6, equal_nan=True),
       "np.log10(x+0.5)", "match")

loge = run_operator(LogTransformStep, [airway],
                    {"base": "e", "pseudocount": 1})
expectede = np.log(airway.data + 1)
record("log_transform(base='e') matches np.log(x+1)",
       np.allclose(loge.data, expectede, atol=1e-6, equal_nan=True),
       "np.log(x+1)", "match")


# ---------------------------------------------------------------- 3
section("3. impute — method-by-method reference")

# use a small matrix with a few NaNs so we can compute exact expectations
rng = np.random.default_rng(7)
data = rng.uniform(2, 20, size=(6, 5)).astype(np.float32)
data[0, 1] = np.nan
data[2, 3] = np.nan
data[4, 0] = np.nan
form = Form(
    data=data,
    dims=["feature", "sample"],
    labels={
        "feature": {f"f{i}": i for i in range(6)},
        "sample": {f"s{i}": i for i in range(5)},
    },
    info={"missing_code": np.nan},
)
# The operator's "dim" names the axis whose entries share a statistic.
# With dim="feature", NaNs in feature row i are filled with feature i's
# mean across the other axis (samples).
imp_mean = run_operator(ImputeStep, [form],
                        {"method": "mean", "dim": "feature"})
row_means = np.nanmean(data, axis=1)
ok = True
for i, j in [(0, 1), (2, 3), (4, 0)]:
    if not np.isclose(imp_mean.data[i, j], row_means[i], atol=1e-5):
        ok = False
record("impute(mean, dim=feature): NaN replaced by feature row mean",
       ok, "np.nanmean(data, axis=1)", "match" if ok else "mismatch")

imp_med = run_operator(ImputeStep, [form],
                       {"method": "median", "dim": "feature"})
row_meds = np.nanmedian(data, axis=1)
ok = True
for i, j in [(0, 1), (2, 3), (4, 0)]:
    if not np.isclose(imp_med.data[i, j], row_meds[i], atol=1e-5):
        ok = False
record("impute(median, dim=feature): NaN replaced by feature row median",
       ok, "np.nanmedian(data, axis=1)", "match" if ok else "mismatch")


# ---------------------------------------------------------------- 4
section("4. compare_groups — reference: scipy.stats")

# Use the airway counts: gene x sample, group_a=untrt, group_b=trt
# The metadata form has a feature axis with label 'dex'
dex_idx = meta.labels["feature"]["dex"]
dex_codes = meta.data[:, dex_idx]
dex_enc = meta.info["encoders"]["feature"]["dex"]
dex_labels = [dex_enc.inverse[int(round(float(c)))] for c in dex_codes]
sample_order = [s for s, _ in sorted(meta.labels["sample"].items(),
                                     key=lambda kv: kv[1])]
group_a_mask = np.array([d == "untrt" for d in dex_labels])
group_b_mask = np.array([d == "trt" for d in dex_labels])

# align masks to the counts sample order
counts_sample_order = [s for s, _ in sorted(airway.labels["sample"].items(),
                                            key=lambda kv: kv[1])]
counts_pos = {s: i for i, s in enumerate(counts_sample_order)}
a_cols = [counts_pos[s] for s, m in zip(sample_order, group_a_mask) if m]
b_cols = [counts_pos[s] for s, m in zip(sample_order, group_b_mask) if m]
print(f"  group_a n={len(a_cols)}  group_b n={len(b_cols)}")

for method, scipy_name in [("ttest", "equal_var=True"),
                           ("welch", "equal_var=False")]:
    out = run_operator(
        CompareGroupsStep, [airway, meta],
        {"dim": "gene", "group_dim": "sample", "group_label": "dex",
         "group_a": "untrt", "group_b": "trt", "method": method,
         "output": "cmp"},
    )
    stat_idx = out.labels["statistic"]["P"]
    statcol = out.labels["statistic"]["stat"]
    mean_a_idx = out.labels["statistic"]["mean_a"]
    mean_b_idx = out.labels["statistic"]["mean_b"]

    # reference on the raw (non-normalized) data
    A = airway.data[:, a_cols]
    B = airway.data[:, b_cols]
    mean_a_ref = np.nanmean(A, axis=1)
    mean_b_ref = np.nanmean(B, axis=1)
    if method == "ttest":
        t_ref, p_ref = stats.ttest_ind(A, B, axis=1, equal_var=True,
                                       nan_policy="omit")
    else:
        t_ref, p_ref = stats.ttest_ind(A, B, axis=1, equal_var=False,
                                       nan_policy="omit")

    # Compare only rows where the operator reported a value. The
    # operator skips genes that cannot be tested (e.g. zero variance in
    # one group); scipy still returns finite values for those.
    def compare_finite(a, b, rtol, atol):
        mask = np.isfinite(a) & np.isfinite(b)
        if not mask.any():
            return False
        return np.allclose(a[mask], b[mask], rtol=rtol, atol=atol)

    mean_a_ok = compare_finite(out.data[:, mean_a_idx], mean_a_ref, 1e-5, 1e-6)
    mean_b_ok = compare_finite(out.data[:, mean_b_idx], mean_b_ref, 1e-5, 1e-6)
    p_ok = compare_finite(out.data[:, stat_idx], p_ref, 1e-4, 1e-12)
    # The operator's "stat" follows log2FC = log2(mean_b / mean_a); scipy
    # ttest_ind(A, B) follows mean_a - mean_b. Same magnitude, opposite
    # sign convention. The two-sided P already covers both directions.
    stat_ok = compare_finite(out.data[:, statcol], -t_ref, 1e-4, 1e-6)

    record(f"compare_groups({method}): mean_a matches np.nanmean",
           mean_a_ok, "np.nanmean(A)", "match" if mean_a_ok else "mismatch")
    record(f"compare_groups({method}): mean_b matches np.nanmean",
           mean_b_ok, "np.nanmean(B)", "match" if mean_b_ok else "mismatch")
    record(f"compare_groups({method}): P matches scipy ({scipy_name})",
           p_ok, "scipy.stats.ttest_ind", "match" if p_ok else "mismatch")
    record(f"compare_groups({method}): stat matches scipy t-statistic",
           stat_ok, "scipy t", "match" if stat_ok else "mismatch")

# mannwhitney
out_mw = run_operator(
    CompareGroupsStep, [airway, meta],
    {"dim": "gene", "group_dim": "sample", "group_label": "dex",
     "group_a": "untrt", "group_b": "trt", "method": "mannwhitney",
     "output": "cmp"},
)
p_idx = out_mw.labels["statistic"]["P"]
A = airway.data[:, a_cols]
B = airway.data[:, b_cols]
mw_p = np.empty(A.shape[0])
for i in range(A.shape[0]):
    try:
        _, p = stats.mannwhitneyu(A[i], B[i], alternative="two-sided")
        mw_p[i] = p
    except ValueError:
        mw_p[i] = np.nan
_mask = np.isfinite(out_mw.data[:, p_idx]) & np.isfinite(mw_p)
p_ok = bool(_mask.any()) and np.allclose(
    out_mw.data[_mask, p_idx], mw_p[_mask], rtol=1e-4, atol=1e-12)
record("compare_groups(mannwhitney): P matches scipy",
       p_ok, "scipy.stats.mannwhitneyu", "match" if p_ok else "mismatch")


# ---------------------------------------------------------------- 5
section("5. correction — reference: statsmodels")

# Use the p-values from the welch comparison as input to correction.
welch = run_operator(
    CompareGroupsStep, [airway, meta],
    {"dim": "gene", "group_dim": "sample", "group_label": "dex",
     "group_a": "untrt", "group_b": "trt", "method": "welch",
     "output": "cmp"},
)
pvalues = welch.data[:, welch.labels["statistic"]["P"]].astype(np.float64)
finite = np.isfinite(pvalues)
print(f"  n finite p-values = {finite.sum()} / {pvalues.size}")

try:
    from statsmodels.stats.multitest import multipletests
    for method_name in ("fdr", "bonferroni"):
        out = run_operator(CorrectionStep, [welch],
                           {"method": method_name,
                            "pfield": "P", "dim": "statistic",
                            "output": "corr"})
        qcol = out.labels["statistic"]["Q_VALUE"]
        sm_method = {"fdr": "fdr_bh", "bonferroni": "bonferroni"}[method_name]
        q_ref = np.full_like(pvalues, np.nan)
        if finite.any():
            _, q_fin, _, _ = multipletests(pvalues[finite], method=sm_method)
            q_ref[finite] = q_fin
        # compare only finite p-values
        ok = np.allclose(out.data[finite, qcol], q_ref[finite], rtol=1e-4,
                         atol=1e-12)
        record(f"correction({method_name}): Q_VALUE matches statsmodels",
               ok, sm_method, "match" if ok else "mismatch")
except ImportError:
    record("correction(fdr): statsmodels installed", False, "yes", "no")


# ---------------------------------------------------------------- 6
section("6. pca — mathematical properties")

pca_out = run_operator(PcaStep, [airway],
                       {"dim": "gene", "n_components": 8})
pc_dim = pca_out.dims[1]
n_pc = pca_out.data.shape[1]
# variance ordering
variances = np.nanvar(pca_out.data, axis=0)
order_ok = bool(np.all(np.diff(variances) <= 1e-6))
record("pca: variance(PC1) >= variance(PC2) >= ...",
       order_ok, "descending", "ascending" if not order_ok else "descending")
# orthogonality of centered components
X = pca_out.data - pca_out.data.mean(axis=0, keepdims=True)
X = np.where(np.isfinite(X), X, 0.0)
gram = X.T @ X
off_diag = gram - np.diag(np.diag(gram))
scale = np.diag(gram).max()
orth_ok = float(np.abs(off_diag).max() / max(scale, 1e-12)) < 1e-4
record("pca: components are orthogonal (off-diag of Gram matrix ~ 0)",
       orth_ok, "~0", f"{np.abs(off_diag).max() / max(scale, 1e-12):.2e}")


# ---------------------------------------------------------------- 7
section("7. reduce_axis — reference: numpy reductions")

# small controlled matrix
rng = np.random.default_rng(11)
mat = rng.uniform(1, 10, size=(4, 6)).astype(np.float32)
mat[0, 0] = np.nan
mat[2, 3] = np.nan
form = Form(
    data=mat,
    dims=["feature", "sample"],
    labels={
        "feature": {f"f{i}": i for i in range(4)},
        "sample": {f"s{i}": i for i in range(6)},
    },
    info={"missing_code": np.nan},
)

for stat_name, np_fn in [
    ("sum", np.nansum),
    ("mean", np.nanmean),
    ("std", np.nanstd),
    ("var", np.nanvar),
    ("min", np.nanmin),
    ("max", np.nanmax),
]:
    out = run_operator(ReduceAxisStep, [form],
                       {"dim": "feature", "stats": stat_name})
    ref = np_fn(mat, axis=0)
    ok = np.allclose(out.data[:, 0], ref, rtol=1e-4, atol=1e-6,
                     equal_nan=True)
    record(f"reduce_axis({stat_name}) matches np.nan{stat_name}",
           ok, f"np.nan{stat_name}", "match" if ok else "mismatch")

# count -> number of non-NaN
out = run_operator(ReduceAxisStep, [form],
                   {"dim": "feature", "stats": "count"})
ref = np.sum(np.isfinite(mat), axis=0).astype(np.float32)
ok = np.allclose(out.data[:, 0], ref)
record("reduce_axis(count) matches np.isfinite sum",
       ok, "np.isfinite sum", "match" if ok else "mismatch")

# nonzero -> count of non-missing and non-zero
out = run_operator(ReduceAxisStep, [form],
                   {"dim": "feature", "stats": "nonzero"})
ref = np.sum(np.isfinite(mat) & (mat != 0), axis=0).astype(np.float32)
ok = np.allclose(out.data[:, 0], ref)
record("reduce_axis(nonzero) matches (finite & non-zero) sum",
       ok, "finite & non-zero", "match" if ok else "mismatch")


# ---------------------------------------------------------------- 8
section("8. rank_axis — reference: np.argsort of variance")

out = run_operator(RankAxisStep, [airway],
                   {"dim": "gene", "by": "variance", "top_n": 200})
# reference: top 200 genes by variance along the sample axis
ref_var = np.nanvar(airway.data, axis=1)
ref_top = np.argsort(-ref_var, kind="stable")[:200]
# operator returns a Form with those 200 genes; compare the label sets
out_labels = set(out.labels["gene"].keys())
pos_to_label = {v: k for k, v in airway.labels["gene"].items()}
ref_labels = {pos_to_label[int(i)] for i in ref_top}
overlap = len(out_labels & ref_labels)
record("rank_axis(variance, top_n=200) labels match np.argsort",
       overlap == 200, "200/200", f"{overlap}/200")


# ---------------------------------------------------------------- 9
section("9. missing — reference: computed missing rate")

out = run_operator(MissingStep, [airway],
                   {"dim": "sample", "threshold": 0.1})
kept_labels = set(out.labels["sample"].keys())
# reference: keep samples whose missing rate <= 0.1
pos_to_label = {v: k for k, v in airway.labels["sample"].items()}
missing_rate = np.isnan(airway.data).sum(axis=0) / airway.data.shape[0]
ref_kept = {pos_to_label[i] for i in range(airway.data.shape[1])
            if missing_rate[i] <= 0.1}
record("missing(dim='sample', threshold=0.1) matches manual computation",
       kept_labels == ref_kept,
       f"{len(ref_kept)} kept", f"{len(kept_labels)} kept")


# ---------------------------------------------------------------- 10
section("10. filter_min — reference: computed pass counts")

out = run_operator(FilterMinStep, [airway],
                   {"dim": "gene", "min_value": 1, "min_samples": 3})
kept_labels = set(out.labels["gene"].keys())
# reference: keep genes with >= 3 samples having >= 1
passing = (airway.data >= 1).sum(axis=1) >= 3
pos_to_label = {v: k for k, v in airway.labels["gene"].items()}
ref_kept = {pos_to_label[i] for i in range(airway.data.shape[0]) if passing[i]}
record("filter_min(dim='gene', min_value=1, min_samples=3) matches manual",
       kept_labels == ref_kept,
       f"{len(ref_kept)} kept", f"{len(kept_labels)} kept")


# ---------------------------------------------------------------- 11
section("11. diversity — reference: scipy.stats.entropy")

# use the microbiome OTU table
otu = read_source(
    "tasks/microbiome_demo/input/OTU_CB_rarefied20k.csv",
    ["species", "sample"],
    {"species": {"sample": 0}, "sample": "builtin"},
)
print(f"  OTU table: {otu.data.shape}, dims={otu.dims}")

for metric_name in ("shannon", "richness"):
    out = run_operator(
        DiversityStep, [otu],
        {"dim": "species", "metrics": metric_name},
    )
    if out.dims[0] == "metric" or "metric" in out.labels:
        # project mode keeps sample on one axis; find the metric row/col
        # The output appends 'metric' axis; the sample axis is on the other
        # dimension. Check labels.
        metric_idx = out.labels["metric"][metric_name] if "metric" in out.labels else 0
        if out.dims == ["sample", "metric"]:
            values = out.data[:, metric_idx]
        else:
            values = out.data[metric_idx, :]
    else:
        values = out.data[:, 0]

    # reference shannon: -sum(p log p) where p = x / sum(x) per sample
    X = otu.data.astype(np.float64)
    X = np.where(np.isfinite(X), X, 0.0)
    if metric_name == "shannon":
        ref = np.array([
            stats.entropy(X[:, j] / X[:, j].sum())
            if X[:, j].sum() > 0 else 0.0
            for j in range(X.shape[1])
        ])
    else:  # richness
        ref = (X > 0).sum(axis=0).astype(np.float64)

    if values.shape[0] == ref.shape[0]:
        ok = np.allclose(values, ref, rtol=1e-4, atol=1e-6)
        record(f"diversity({metric_name}) matches reference",
               ok, metric_name, "match" if ok else "mismatch")
    else:
        record(f"diversity({metric_name}) shape alignment", False,
               f"len {ref.shape[0]}", f"len {values.shape[0]}")


# ---------------------------------------------------------------- 12
section("12. distance_matrix — reference: scipy.spatial.distance")

out = run_operator(DistanceMatrixStep, [airway],
                   {"dim": "sample", "metric": "euclidean"})
print(f"  distance matrix shape: {out.data.shape}")

# reference: pdist on the transposed matrix (samples as rows)
X = airway.data.T.astype(np.float64)
X = np.where(np.isfinite(X), X, 0.0)
ref = scipy_distance.squareform(scipy_distance.pdist(X, metric="euclidean"))
ok = np.allclose(out.data, ref, rtol=1e-3, atol=1e-4)
record("distance_matrix(euclidean) matches scipy.spatial.distance",
       ok, "scipy pdist", "match" if ok else "mismatch")


# ---------------------------------------------------------------- 13
section("13. correlation — reference: np.corrcoef")

out = run_operator(CorrelationStep, [airway],
                   {"dim": "sample", "metric": "pearson"})
X = airway.data.T.astype(np.float64)  # samples as rows
ref = np.corrcoef(X)
ok = np.allclose(out.data, ref, rtol=1e-3, atol=1e-4, equal_nan=True)
record("correlation(pearson) matches np.corrcoef",
       ok, "np.corrcoef", "match" if ok else "mismatch")


# ---------------------------------------------------------------- summary
print()
print("=" * 78)
print("Verification summary")
print("=" * 78)
n_pass = sum(1 for _, ok, _, _ in checks if ok)
print(f"{'':4s}{'check':<62s}{'expected':<20s}{'actual':<24s}")
print("-" * 78)
for name, ok, exp, act in checks:
    status = "PASS" if ok else "FAIL"
    print(f"{status:4s}  {name:<60s}  {exp:<18s}  {act:<22s}")
print("-" * 78)
print(f"{n_pass}/{len(checks)} checks passed")
