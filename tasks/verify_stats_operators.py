"""Verification of statistical operators against scipy / statsmodels /
lifelines / sklearn / networkx references.

Run with: python tasks/verify_stats_operators.py
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

from src.task.step.steps.reduce import ReduceStep
from src.task.step.steps.cluster_axis import ClusterAxisStep
from src.task.step.steps.permanova import PermanovaStep
from src.task.step.steps.logrank_test import LogrankTestStep
from src.task.step.steps.cox_regression import CoxRegressionStep
from src.task.step.steps.enrich_go import EnrichGoStep


checks = []


def record(name, ok, expected, actual):
    checks.append((name, bool(ok), str(expected)[:52], str(actual)[:52]))


def section(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


# ---------------------------------------------------------------- shared data
airway = read_source(
    "tasks/rnaseq_de_demo/input/airway_counts.csv",
    ["gene", "sample"],
    {"gene": {"sample": 0}, "sample": "builtin"},
)
print(f"airway : {airway.data.shape}, dims={airway.dims}")


# ---------------------------------------------------------------- 1 reduce PCA
section("1. reduce(pca) — reference: sklearn PCA")

# Take a small subset so sklearn PCA (which centers internally) matches
# the operator's implementation exactly.
subset = airway.subset_axis("gene", list(range(200)))
out = run_operator(ReduceStep, [subset],
                   {"dim": "gene", "method": "pca",
                    "n_components": 5, "standardize": False,
                    "output": "out"})
print(f"reduce(pca) output: {out.data.shape}, dims={out.dims}")

from sklearn.decomposition import PCA
X = subset.data.T.astype(np.float64)   # samples as rows
pca = PCA(n_components=5, random_state=0)
scores_ref = pca.fit_transform(X)

# Operator's scores might have flipped signs per component; take abs on
# the correlation per component instead.
op = out.data
ok_components = op.shape == scores_ref.shape
record("reduce(pca): 5 components for 8 samples",
       ok_components, scores_ref.shape, op.shape)

# Check per-component correlation between operator and reference.
corrs = []
for k in range(5):
    r = np.corrcoef(op[:, k], scores_ref[:, k])[0, 1]
    corrs.append(abs(r))
ok_corr = all(abs(c - 1.0) < 1e-4 for c in corrs)
record("reduce(pca): each component correlates |r|=1 with sklearn",
       ok_corr, "all |r|=1", f"min |r| = {min(corrs):.6f}")


# ---------------------------------------------------------------- 2 reduce PCoA
section("2. reduce(pcoa) — reference: classical MDS on Euclidean distances")

subset = airway.subset_axis("gene", list(range(200)))
# PCoA needs a precomputed square distance matrix.
X = subset.data.T.astype(np.float64)   # (n_samples, n_genes)
D = scipy_distance.squareform(scipy_distance.pdist(X, "euclidean"))
n = D.shape[0]
dist_form = Form(
    data=D.astype(np.float32),
    dims=["sample", "sample_b"],
    labels={
        "sample": dict(subset.labels["sample"]),
        "sample_b": dict(subset.labels["sample"]),
    },
    info={"missing_code": np.nan, "representation": "distance"},
)
out = run_operator(ReduceStep, [dist_form],
                   {"dim": "sample", "method": "pcoa",
                    "n_components": 5, "standardize": False,
                    "output": "out"})
print(f"reduce(pcoa) output: {out.data.shape}, dims={out.dims}")

# Classical MDS reference: double-center squared Euclidean distance
D2 = D ** 2
J = np.eye(n) - np.ones((n, n)) / n
B = -0.5 * J @ D2 @ J
eigvals, eigvecs = np.linalg.eigh(B)
order = np.argsort(eigvals)[::-1]
eigvals = eigvals[order]
eigvecs = eigvecs[:, order]
scores_ref = eigvecs[:, :5] * np.sqrt(np.maximum(eigvals[:5], 0))

op = out.data
corrs = []
for k in range(5):
    r = np.corrcoef(op[:, k], scores_ref[:, k])[0, 1]
    corrs.append(abs(r))
ok_corr = all(abs(c - 1.0) < 1e-3 for c in corrs)
record("reduce(pcoa): each component correlates |r|=1 with classical MDS",
       ok_corr, "all |r|=1", f"min |r| = {min(corrs):.6f}")


# ---------------------------------------------------------------- 3 cluster_axis kmeans
section("3. cluster_axis(kmeans) — reference: sklearn KMeans")

# Build a small dataset with clear structure: 3 well-separated blobs.
rng = np.random.default_rng(0)
blob_a = rng.normal([0, 0, 0, 0], 0.3, size=(20, 4))
blob_b = rng.normal([5, 5, 5, 5], 0.3, size=(20, 4))
blob_c = rng.normal([10, 0, 0, 10], 0.3, size=(20, 4))
X = np.vstack([blob_a, blob_b, blob_c]).astype(np.float32)

form = Form(
    data=X,
    dims=["sample", "feature"],
    labels={
        "sample": {f"s{i}": i for i in range(60)},
        "feature": {f"f{i}": i for i in range(4)},
    },
    info={"missing_code": np.nan},
)

out = run_operator(ClusterAxisStep, [form],
                   {"dim": "sample", "method": "kmeans", "n_clusters": 3,
                    "random_state": 0, "output": "out"})
print(f"cluster_axis output: {out.data.shape}, dims={out.dims}")
print(f"cluster label distribution:")
col = out.data[:, 0] if out.data.ndim == 2 else out.data
for k in np.unique(col):
    print(f"  cluster {int(k)}: {int((col == k).sum())} samples")

# Reference: sklearn KMeans on the same data
from sklearn.cluster import KMeans
km = KMeans(n_clusters=3, random_state=0, n_init=10)
labels_ref = km.fit_predict(X)

# Compare: the operator might use different label IDs; compare the
# partitions via adjusted Rand index.
from sklearn.metrics import adjusted_rand_score
labels_op = col.astype(int)
ari = adjusted_rand_score(labels_ref, labels_op)
record("cluster_axis(kmeans): ARI vs sklearn KMeans = 1.0",
       abs(ari - 1.0) < 1e-6, 1.0, f"{ari:.6f}")


# ---------------------------------------------------------------- 4 permanova
section("4. permanova — reference: manual Anderson 2001")

# 30 samples, 3 groups. Compute a distance matrix, then PERMANOVA
# overall F statistic and p-value using permutations.
rng = np.random.default_rng(42)
group_labels = ["A"] * 10 + ["B"] * 10 + ["C"] * 10
# Shift each group so F is large.
vals = rng.normal(0, 1, size=(30, 4))
vals[10:20] += 2
vals[20:30] += 4

otu = Form(
    data=vals.astype(np.float32),
    dims=["sample", "feature"],
    labels={
        "sample": {f"s{i}": i for i in range(30)},
        "feature": {f"f{i}": i for i in range(4)},
    },
    info={"missing_code": np.nan},
)

# Distance matrix Form
from scipy.spatial.distance import pdist, squareform
D = squareform(pdist(vals, "euclidean")).astype(np.float32)
dist_form = Form(
    data=D,
    dims=["sample", "sample_b"],
    labels={"sample": {f"s{i}": i for i in range(30)},
            "sample_b": {f"s{i}": i for i in range(30)}},
    info={"missing_code": np.nan, "representation": "distance"},
)

# Group metadata Form (sample, feature) with a categorical 'group' column
from src.reader.readers._encoder import get_encoder
grp_enc = get_encoder("labelencoder")
grp_codes = grp_enc.fit_transform(group_labels)
grp_form = Form(
    data=grp_codes.reshape(-1, 1).astype(np.float32),
    dims=["sample", "feature"],
    labels={"sample": {f"s{i}": i for i in range(30)},
            "feature": {"group": 0}},
    info={"missing_code": np.nan,
          "encoders": {"feature": {"group": grp_enc}}},
)

out = run_operator(PermanovaStep, [dist_form, grp_form],
                   {"dist_dim": "sample", "group_dim": "sample",
                    "group_label": "group",
                    "groups": ["A", "B", "C"], "pairwise": False,
                    "n_permutations": 999, "random_state": 0,
                    "output": "out"})
print(f"permanova output: shape={out.data.shape}, "
      f"labels={out.labels['statistic']}")
F_op = float(out.data[0, out.labels["statistic"]["F"]])
R2_op = float(out.data[0, out.labels["statistic"]["R2"]])
P_op = float(out.data[0, out.labels["statistic"]["P"]])
print(f"  F  = {F_op:.4f}")
print(f"  R2 = {R2_op:.4f}")
print(f"  P  = {P_op:.4f}")

# Manual Anderson 2001 reference
def permanova_ref(D, groups, n_perm=999, seed=0):
    D2 = D ** 2
    n = D2.shape[0]
    unique_groups = sorted(set(groups))
    a = len(unique_groups)
    # SS_total (trace of double-centered matrix / n)
    total_ss = D2.sum() / (2 * n)
    # Within-group SS
    within_ss = 0.0
    for g in unique_groups:
        idx = [i for i, x in enumerate(groups) if x == g]
        ng = len(idx)
        if ng < 2:
            continue
        sub = D2[np.ix_(idx, idx)]
        within_ss += sub.sum() / (2 * ng)
    between_ss = total_ss - within_ss
    F = (between_ss / (a - 1)) / (within_ss / (n - a))
    R2 = between_ss / total_ss
    # Permutations
    rng = np.random.default_rng(seed)
    exceed = 1
    for _ in range(n_perm):
        perm = rng.permutation(n)
        pg = [groups[perm[i]] for i in range(n)]
        w = 0.0
        for g in unique_groups:
            idx = [i for i, x in enumerate(pg) if x == g]
            ng = len(idx)
            if ng < 2:
                continue
            sub = D2[np.ix_(idx, idx)]
            w += sub.sum() / (2 * ng)
        Fp = ((total_ss - w) / (a - 1)) / (w / (n - a))
        if Fp >= F:
            exceed += 1
    P = exceed / (n_perm + 1)
    return F, R2, P


F_ref, R2_ref, P_ref = permanova_ref(D.astype(np.float64), group_labels)
print(f"reference F = {F_ref:.4f}, R2 = {R2_ref:.4f}, P = {P_ref:.4f}")
record("permanova: F matches Anderson 2001 reference",
       abs(F_op - F_ref) < 1e-2 * max(1.0, abs(F_ref)),
       f"{F_ref:.4f}", f"{F_op:.4f}")
record("permanova: R2 matches reference",
       abs(R2_op - R2_ref) < 1e-2 * max(1.0, abs(R2_ref)),
       f"{R2_ref:.4f}", f"{R2_op:.4f}")


# ---------------------------------------------------------------- 5 logrank
section("5. logrank_test — reference: lifelines")

from lifelines.statistics import logrank_test as ll_logrank

rng = np.random.default_rng(7)
n = 80
group = np.array([0] * 40 + [1] * 40)
# group 1 survives longer
times = rng.exponential(np.where(group == 0, 40, 70)) + 1
events = rng.binomial(1, 0.85, n)

clinical = Form(
    data=np.column_stack([times, events, group]).astype(np.float32),
    dims=["sample", "feature"],
    labels={
        "sample": {f"s{i}": i for i in range(n)},
        "feature": {"time": 0, "event": 1, "group": 2},
    },
    info={"missing_code": np.nan},
)

out = run_operator(LogrankTestStep, [clinical],
                   {"time_label": "time", "event_label": "event",
                    "group_label": "group", "pairwise": False,
                    "output": "out"})
print(f"logrank output: shape={out.data.shape}, "
      f"labels={out.labels['statistic']}")
P_op = float(out.data[0, out.labels["statistic"]["P"]])

# lifelines reference
res = ll_logrank(
    times[group == 0], times[group == 1],
    event_observed_A=events[group == 0],
    event_observed_B=events[group == 1],
)
P_ref = float(res.p_value)
print(f"lifelines P = {P_ref:.6f}")
record("logrank_test: P matches lifelines",
       abs(P_op - P_ref) < 1e-3, f"{P_ref:.6f}", f"{P_op:.6f}")


# ---------------------------------------------------------------- 6 cox
section("6. cox_regression — reference: lifelines CoxPHFitter")

from lifelines import CoxPHFitter

rng = np.random.default_rng(11)
n = 120
age = rng.normal(60, 8, n)
grp = rng.binomial(1, 0.5, n)
# Simple Cox model: hazard ~ exp(0.03*(age-60) + 0.7*grp)
base_haz = rng.exponential(50, n)
times = base_haz * np.exp(-0.03 * (age - 60) - 0.7 * grp)
events = rng.binomial(1, 0.8, n)

clinical = Form(
    data=np.column_stack([times, events, age, grp]).astype(np.float32),
    dims=["sample", "feature"],
    labels={
        "sample": {f"s{i}": i for i in range(n)},
        "feature": {"time": 0, "event": 1, "age": 2, "grp": 3},
    },
    info={"missing_code": np.nan},
)

out = run_operator(CoxRegressionStep, [clinical],
                   {"time_label": "time", "event_label": "event",
                    "covariates": ["age", "grp"],
                    "output": "out"})
print(f"cox output: shape={out.data.shape}, "
      f"cov labels={out.labels['covariate']}")
HR_op = np.array([
    out.data[out.labels["covariate"]["age"], out.labels["statistic"]["HR"]],
    out.data[out.labels["covariate"]["grp"], out.labels["statistic"]["HR"]],
])
print(f"operator HR = {HR_op}")

# lifelines reference
import pandas as pd
df = pd.DataFrame({"time": times, "event": events, "age": age, "grp": grp})
cph = CoxPHFitter()
cph.fit(df, duration_col="time", event_col="event")
HR_ref = cph.hazard_ratios_[["age", "grp"]].to_numpy()
print(f"lifelines HR = {HR_ref}")

ok = np.allclose(HR_op, HR_ref, rtol=1e-3, atol=1e-3)
record("cox_regression: HR matches lifelines CoxPHFitter",
       ok, HR_ref.tolist(), HR_op.tolist())


# ---------------------------------------------------------------- 7 enrich_go
section("7. enrich_go — reference: scipy.stats.hypergeom + multipletests")

# Build a small universe / hits pair: 20 genes x 5 GO terms
rng = np.random.default_rng(3)
universe = np.zeros((20, 5), dtype=np.float32)
for i in range(20):
    for j in rng.choice(5, size=2, replace=False):
        universe[i, j] = 1.0
hit_positions = np.random.choice(20, 6, replace=False)
hits = universe[hit_positions].copy()
# Make terms 0 and 1 strongly over-represented
hits[0:4, 0] = 1.0
hits[0:3, 1] = 1.0

u = Form(
    data=universe,
    dims=["gene", "go_term"],
    labels={"gene": {f"g{i}": i for i in range(20)},
            "go_term": {f"GO:{j}": j for j in range(5)}},
    info={"missing_code": np.nan, "representation": "binary"},
)
# Hit genes must be a subset of the universe genes by label.
# Use the same gene labels for the selected rows.
hit_gene_labels = {f"g{int(p)}": i for i, p in enumerate(hit_positions)}
h = Form(
    data=hits,
    dims=["gene", "go_term"],
    labels={"gene": hit_gene_labels,
            "go_term": {f"GO:{j}": j for j in range(5)}},
    info={"missing_code": np.nan, "representation": "binary"},
)

out = run_operator(EnrichGoStep, [h, u],
                   {"gene_dim": "gene", "term_dim": "go_term",
                    "correction": "fdr", "min_term_size": 1,
                    "output": "out"})
print(f"enrich_go output: shape={out.data.shape}, "
      f"stat labels={out.labels['statistic']}")

q_col = out.labels["statistic"]["Q_VALUE"]
p_col = out.labels["statistic"]["P_VALUE"]
term_labels = [k for k, _ in sorted(out.labels["go_term"].items(),
                                     key=lambda kv: kv[1])]

# Reference: hypergeometric test for each term
N = 20  # universe size (all genes)
n_hits = 6  # total hits genes
P_ref = []
K_list = []
k_list = []
for j in range(5):
    K = int(universe[:, j].sum())
    k = int(hits[:, j].sum())
    K_list.append(K)
    k_list.append(k)
    # P(X >= k)
    p = float(stats.hypergeom.sf(k - 1, N, K, n_hits))
    P_ref.append(p)
P_ref = np.array(P_ref)

from statsmodels.stats.multitest import multipletests
Q_ref = multipletests(P_ref, method="fdr_bh")[1]

op_P = np.array([out.data[out.labels["go_term"][t], p_col] for t in term_labels])
op_Q = np.array([out.data[out.labels["go_term"][t], q_col] for t in term_labels])

print(f"  ref P = {P_ref}")
print(f"  op  P = {op_P}")
ok_p = np.allclose(op_P, P_ref, rtol=1e-4, atol=1e-9)
record("enrich_go: hypergeometric P matches scipy.stats.hypergeom",
       ok_p, "scipy hypergeom", "match" if ok_p else "differ")
ok_q = np.allclose(op_Q, Q_ref, rtol=1e-4, atol=1e-9)
record("enrich_go: FDR Q matches statsmodels multipletests fdr_bh",
       ok_q, "statsmodels fdr_bh", "match" if ok_q else "differ")


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
