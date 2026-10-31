"""R-backed external oracles for the optional statistical operators.

These tests are skipped when Rscript is unavailable.  Package-backed tests are
also skipped when the relevant R package is not installed, so the default
Python-only test environment remains usable.
"""
from __future__ import annotations

import shutil
import subprocess
from functools import lru_cache

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.gsea import GseaStep
from src.task.step.steps.limma_de import LimmaDeStep
from src.task.step.steps.meta_analysis import MetaAnalysisStep
from src.task.step.steps.ora import OraStep

RSCRIPT = shutil.which("Rscript")


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels, dtype=np.float32):
    value = Form(np.asarray(data, dtype=dtype), list(dims), labels,
                 {"missing_code": np.nan})
    value.validate()
    return value


def _run_step(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


@lru_cache(maxsize=1)
def _r_packages() -> frozenset[str]:
    if RSCRIPT is None:
        return frozenset()
    proc = subprocess.run(
        [RSCRIPT, "--no-save", "--no-restore", "-e",
         "cat(rownames(installed.packages()), sep='\\n')"],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        return frozenset()
    return frozenset(line.strip() for line in proc.stdout.splitlines() if line.strip())


def _requires_r(*packages: str):
    missing = sorted(p for p in packages if p not in _r_packages())
    reason = "Rscript not found" if RSCRIPT is None else f"R package(s) not installed: {missing}"
    return pytest.mark.skipif(RSCRIPT is None or bool(missing), reason=reason)


def _run_r(tmp_path, script: str):
    path = tmp_path / "oracle.R"
    path.write_text(script, encoding="utf-8")
    proc = subprocess.run(
        [RSCRIPT, "--no-save", "--no-restore", str(path)],
        cwd=tmp_path, capture_output=True, text=True, timeout=180,
    )
    if proc.returncode != 0:
        pytest.fail(
            "R oracle failed\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc


def _metadata(groups):
    samples = [f"s{i}" for i in range(len(groups))]
    return _form(
        np.asarray(groups, dtype=object).reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {s: i for i, s in enumerate(samples)}, "feature": {"group": 0}},
        dtype=object,
    ), samples


def _sample_form(data, samples):
    return _form(
        data, ["protein", "sample"],
        {"protein": {f"p{i}": i for i in range(data.shape[0])},
         "sample": {s: i for i, s in enumerate(samples)}},
    )


@_requires_r("limma")
def test_limma_logfc_t_p_match_r_lmfit(tmp_path):
    rng = np.random.default_rng(41)
    data = rng.normal(5.0, 0.7, (6, 6)).astype(np.float32)
    data[:3, 3:] += 1.8
    samples = [f"s{i}" for i in range(6)]
    pd.DataFrame(data, index=[f"p{i}" for i in range(6)], columns=samples).to_csv(
        tmp_path / "values.csv"
    )
    script = r'''
suppressPackageStartupMessages(library(limma))
x <- as.matrix(read.csv("values.csv", row.names = 1, check.names = FALSE))
group <- factor(rep(c("a", "b"), each = 3))
design <- model.matrix(~0 + group)
colnames(design) <- levels(group)
fit <- lmFit(x, design)
fit <- contrasts.fit(fit, makeContrasts(b - a, levels = design))
se <- as.numeric(fit$stdev.unscaled[, 1] * fit$sigma)
tval <- as.numeric(fit$coefficients[, 1] / se)
pval <- 2 * pt(-abs(tval), df = fit$df.residual)
res <- data.frame(
  feature = rownames(x),
  logFC = as.numeric(fit$coefficients[, 1]),
  t = tval,
  p = pval
)
write.csv(res, "limma.csv", row.names = FALSE)
'''
    _run_r(tmp_path, script)
    reference = pd.read_csv(tmp_path / "limma.csv")
    meta, _ = _metadata(["a", "a", "a", "b", "b", "b"])
    out, _ = _run_step(
        LimmaDeStep(),
        {"feature_dim": "protein", "sample_dim": "sample", "group_label": "group",
         "group_a": "a", "group_b": "b", "prior_df": 0, "output": "limma"},
        [_sample_form(data, samples), meta],
    )
    np.testing.assert_allclose(out.data[:, 0], reference["logFC"], rtol=2e-5, atol=1e-6)
    np.testing.assert_allclose(out.data[:, 3], reference["t"], rtol=2e-5, atol=1e-6)
    np.testing.assert_allclose(out.data[:, 4], reference["p"], rtol=2e-5, atol=1e-8)


@_requires_r()
def test_ora_hypergeometric_matches_r_phyper(tmp_path):
    genes = [f"g{i}" for i in range(30)]
    stats = np.zeros((30, 2), dtype=np.float32)
    stats[:6, 1] = 0.01
    stats[6:, 1] = 0.50
    sets = np.zeros((30, 2), dtype=np.float32)
    sets[:10, 0] = 1
    sets[10:20, 1] = 1
    out, export = _run_step(
        OraStep(),
        {"p_label": "Q_VALUE", "lfc_label": "log2FC", "p_threshold": 0.05,
         "output": "ora"},
        [_form(stats, ["gene", "statistic"],
               {"gene": {g: i for i, g in enumerate(genes)},
                "statistic": {"log2FC": 0, "Q_VALUE": 1}}),
         _form(sets, ["gene", "gene_set"],
               {"gene": {g: i for i, g in enumerate(genes)},
                "gene_set": {"A": 0, "B": 1}})],
    )
    assert export["universe"] == 30 and export["hits"] == 6
    assert [r["set_size"] for r in export["results"]] == [10, 10]
    script = r'''
N <- 30
hit_n <- 6
K <- c(10, 10)
k <- c(6, 0)
p <- phyper(k - 1, K, N - K, hit_n, lower.tail = FALSE)
write.csv(data.frame(set = c("A", "B"), p = p), "ora.csv", row.names = FALSE)
'''
    _run_r(tmp_path, script)
    reference = pd.read_csv(tmp_path / "ora.csv")
    np.testing.assert_allclose(out.data[:, 3], reference["p"], rtol=1e-6, atol=1e-10)


@_requires_r("fgsea")
def test_gsea_enrichment_score_matches_fgsea(tmp_path):
    rng = np.random.default_rng(7)
    genes = [f"g{i}" for i in range(40)]
    values = np.linspace(3.0, -3.0, len(genes)) + rng.normal(0, 0.01, len(genes))
    genes_form = _form(
        np.column_stack([values, np.full(len(genes), 0.01)]),
        ["gene", "statistic"],
        {"gene": {g: i for i, g in enumerate(genes)},
         "statistic": {"log2FC": 0, "Q_VALUE": 1}},
    )
    sets = np.zeros((len(genes), 1), dtype=np.float32)
    sets[:6, 0] = 1
    sets_form = _form(sets, ["gene", "gene_set"],
                      {"gene": {g: i for i, g in enumerate(genes)},
                       "gene_set": {"TOP": 0}})
    out, export = _run_step(
        GseaStep(),
        {"rank_label": "log2FC", "n_permutations": 10, "min_set_size": 3,
         "max_set_size": 10, "seed": 1, "output": "gsea"},
        [genes_form, sets_form],
    )
    assert export["sets_tested"] == 1
    pd.DataFrame({"gene": genes, "stat": values}).to_csv(tmp_path / "stats.csv", index=False)
    script = r'''
suppressPackageStartupMessages(library(fgsea))
d <- read.csv("stats.csv", stringsAsFactors = FALSE)
v <- setNames(d$stat, d$gene)
v <- sort(v, decreasing = TRUE)
selected <- which(names(v) %in% c("g0", "g1", "g2", "g3", "g4", "g5"))
cat(as.numeric(calcGseaStat(v, selected, gseaParam = 1)), "\n")
'''
    proc = _run_r(tmp_path, script)
    reference = float(proc.stdout.strip())
    assert out.data[0, 0] == pytest.approx(reference, rel=1e-6, abs=1e-7)


@_requires_r("metafor")
def test_meta_analysis_fixed_and_random_match_metafor(tmp_path):
    effects = np.array([
        [0.20, 0.40, 0.30, 0.50],
        [0.10, -0.20, 0.00, 0.40],
        [-0.30, 0.10, 0.20, -0.10],
    ], dtype=np.float32)
    stds = np.array([
        [0.10, 0.20, 0.15, 0.30],
        [0.20, 0.10, 0.25, 0.20],
        [0.15, 0.20, 0.10, 0.30],
    ], dtype=np.float32)
    variants = {f"v{i}": i for i in range(3)}
    studies = {f"s{i}": i for i in range(4)}
    pd.DataFrame(effects, index=list(variants), columns=list(studies)).to_csv(
        tmp_path / "effects.csv"
    )
    pd.DataFrame(stds, index=list(variants), columns=list(studies)).to_csv(
        tmp_path / "stds.csv"
    )
    script = r'''
suppressPackageStartupMessages(library(metafor))
e <- as.matrix(read.csv("effects.csv", row.names = 1, check.names = FALSE))
s <- as.matrix(read.csv("stds.csv", row.names = 1, check.names = FALSE))
rows <- lapply(seq_len(nrow(e)), function(i) {
  fe <- rma(yi = e[i, ], sei = s[i, ], method = "FE")
  dl <- rma(yi = e[i, ], sei = s[i, ], method = "DL")
  data.frame(variant = rownames(e)[i],
             fe_beta = fe$beta, fe_se = fe$se, fe_z = fe$zval, fe_p = fe$pval,
             dl_beta = dl$beta, dl_se = dl$se, dl_z = dl$zval, dl_p = dl$pval,
             Q = dl$QE, I2 = dl$I2)
})
write.csv(do.call(rbind, rows), "meta.csv", row.names = FALSE)
'''
    _run_r(tmp_path, script)
    reference = pd.read_csv(tmp_path / "meta.csv")
    effects_form = _form(effects, ["variant", "study"],
                         {"variant": variants, "study": studies})
    stds_form = _form(stds, ["variant", "study"],
                      {"variant": variants, "study": studies})
    out, _ = _run_step(MetaAnalysisStep(), {"method": "random"}, [effects_form, stds_form])
    columns = out.labels["statistic"]
    np.testing.assert_allclose(out.data[:, columns["beta"]], reference["dl_beta"], rtol=1e-6, atol=1e-8)
    np.testing.assert_allclose(out.data[:, columns["se"]], reference["dl_se"], rtol=1e-6, atol=1e-8)
    np.testing.assert_allclose(out.data[:, columns["z"]], reference["dl_z"], rtol=1e-6, atol=1e-7)
    np.testing.assert_allclose(out.data[:, columns["P_VALUE"]], reference["dl_p"], rtol=1e-6, atol=1e-10)
    np.testing.assert_allclose(out.data[:, columns["Q"]], reference["Q"], rtol=1e-6, atol=1e-8)
    np.testing.assert_allclose(out.data[:, columns["I2"]], reference["I2"], rtol=1e-6, atol=1e-8)

    out_fixed, _ = _run_step(MetaAnalysisStep(), {"method": "fixed"}, [effects_form, stds_form])
    np.testing.assert_allclose(out_fixed.data[:, columns["beta"]], reference["fe_beta"], rtol=1e-6, atol=1e-8)
    np.testing.assert_allclose(out_fixed.data[:, columns["se"]], reference["fe_se"], rtol=1e-6, atol=1e-8)
    np.testing.assert_allclose(out_fixed.data[:, columns["z"]], reference["fe_z"], rtol=1e-6, atol=1e-7)
    np.testing.assert_allclose(out_fixed.data[:, columns["P_VALUE"]], reference["fe_p"], rtol=1e-6, atol=1e-10)

@_requires_r()
def test_ancom_style_matches_independent_r_logratio(tmp_path):
    from src.task.step.steps.ancom_bc import AncomBcStep

    counts = np.array([
        [10, 2, 4], [12, 1, 5], [11, 3, 3],
        [30, 10, 7], [28, 8, 8], [32, 9, 6],
    ], dtype=np.float32)
    samples = [f"s{i}" for i in range(6)]
    taxa = ["t1", "t2", "t3"]
    pd.DataFrame(counts, index=samples, columns=taxa).to_csv(tmp_path / "counts.csv")
    pd.DataFrame({"sample": samples, "group": ["a"] * 3 + ["b"] * 3}).to_csv(
        tmp_path / "groups.csv", index=False
    )
    script = r'''
x <- as.matrix(read.csv("counts.csv", row.names = 1, check.names = FALSE))
g <- read.csv("groups.csv", stringsAsFactors = FALSE)$group
la <- log(x[g == "a", , drop = FALSE] + 1)
lb <- log(x[g == "b", , drop = FALSE] + 1)
la <- la - rowMeans(la)
lb <- lb - rowMeans(lb)
diff <- colMeans(lb) - colMeans(la)
p <- vapply(seq_len(ncol(x)), function(j) {
  t.test(la[, j], lb[, j], var.equal = FALSE)$p.value
}, numeric(1))
write.csv(data.frame(taxon = colnames(x), diff = diff, p = p), "ancom.csv", row.names = FALSE)
'''
    _run_r(tmp_path, script)
    reference = pd.read_csv(tmp_path / "ancom.csv")
    meta = _form(
        np.array([["a"], ["a"], ["a"], ["b"], ["b"], ["b"]], dtype=object),
        ["sample", "feature"],
        {"sample": {s: i for i, s in enumerate(samples)}, "feature": {"group": 0}},
        dtype=object,
    )
    table = _form(counts, ["sample", "taxon"],
                  {"sample": {s: i for i, s in enumerate(samples)},
                   "taxon": {t: i for i, t in enumerate(taxa)}})
    out, _ = _run_step(
        AncomBcStep(),
        {"group_label": "group", "group_a": "a", "group_b": "b", "pseudocount": 1.0},
        [table, meta],
    )
    np.testing.assert_allclose(out.data[:, 0], reference["diff"], rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(out.data[:, 2], reference["p"], rtol=1e-5, atol=1e-8)


@_requires_r("GSVA")
def test_ssgsea_matches_r_gsva(tmp_path):
    from src.task.step.steps.ssgsea import SsgseaStep

    counts = np.array([
        [1.0, 2.0, 3.0, 4.0],
        [2.0, 1.0, 4.0, 3.0],
        [5.0, 4.0, 2.0, 1.0],
        [3.0, 6.0, 1.0, 5.0],
        [4.0, 3.0, 6.0, 2.0],
        [6.0, 5.0, 4.0, 7.0],
    ], dtype=np.float32)
    genes = [f"g{i}" for i in range(6)]
    samples = [f"s{i}" for i in range(4)]
    pd.DataFrame(counts, index=genes, columns=samples).to_csv(tmp_path / "expr.csv")
    script = r'''
suppressPackageStartupMessages(library(GSVA))
x <- as.matrix(read.csv("expr.csv", row.names = 1, check.names = FALSE))
sets <- list(A = c("g0", "g1", "g2"), B = c("g3", "g4", "g5"))
res <- gsva(ssgseaParam(x, sets, minSize = 1, alpha = 0.25, normalize = TRUE), verbose = FALSE)
write.csv(as.data.frame(res), "ssgsea.csv")
'''
    _run_r(tmp_path, script)
    reference = pd.read_csv(tmp_path / "ssgsea.csv", index_col=0)
    sets = np.zeros((6, 2), dtype=np.float32)
    sets[:3, 0] = 1
    sets[3:, 1] = 1
    expr = _form(counts, ["gene", "sample"],
                 {"gene": {g: i for i, g in enumerate(genes)},
                  "sample": {s: i for i, s in enumerate(samples)}})
    sets_form = _form(sets, ["gene", "gene_set"],
                      {"gene": {g: i for i, g in enumerate(genes)},
                       "gene_set": {"A": 0, "B": 1}})
    out, _ = _run_step(
        SsgseaStep(),
        {"feature_dim": "gene", "sample_dim": "sample", "gene_dim": "gene",
         "gene_set_dim": "gene_set", "alpha": 0.25, "min_size": 1,
         "normalize": True},
        [expr, sets_form],
    )
    np.testing.assert_allclose(out.data, reference.T.to_numpy(), rtol=1e-5, atol=1e-6)


@_requires_r()
def test_aldex_clr_non_mc_matches_independent_r(tmp_path):
    from src.task.step.steps.aldex2 import Aldex2Step

    counts = np.array([
        [10, 2, 4], [12, 1, 5], [11, 3, 3],
        [30, 10, 7], [28, 8, 8], [32, 9, 6],
    ], dtype=np.float32)
    samples = [f"s{i}" for i in range(6)]
    taxa = ["t1", "t2", "t3"]
    pd.DataFrame(counts, index=samples, columns=taxa).to_csv(tmp_path / "counts.csv")
    pd.DataFrame({"sample": samples, "group": ["a"] * 3 + ["b"] * 3}).to_csv(
        tmp_path / "groups.csv", index=False
    )
    script = r'''
x <- as.matrix(read.csv("counts.csv", row.names = 1, check.names = FALSE))
g <- read.csv("groups.csv", stringsAsFactors = FALSE)$group
la <- log(x[g == "a", , drop = FALSE] + 0.5)
lb <- log(x[g == "b", , drop = FALSE] + 0.5)
la <- la - rowMeans(la)
lb <- lb - rowMeans(lb)
diff <- colMeans(lb) - colMeans(la)
p <- vapply(seq_len(ncol(x)), function(j) {
  t.test(la[, j], lb[, j], var.equal = FALSE)$p.value
}, numeric(1))
write.csv(data.frame(taxon = colnames(x), diff = diff, p = p), "aldex.csv", row.names = FALSE)
'''
    _run_r(tmp_path, script)
    reference = pd.read_csv(tmp_path / "aldex.csv")
    meta = _form(
        np.array([["a"], ["a"], ["a"], ["b"], ["b"], ["b"]], dtype=object),
        ["sample", "feature"],
        {"sample": {s: i for i, s in enumerate(samples)}, "feature": {"group": 0}},
        dtype=object,
    )
    table = _form(counts, ["sample", "taxon"],
                  {"sample": {s: i for i, s in enumerate(samples)},
                   "taxon": {t: i for i, t in enumerate(taxa)}})
    out, _ = _run_step(
        Aldex2Step(),
        {"group_label": "group", "group_a": "a", "group_b": "b", "pseudocount": 0.5,
         "monte_carlo": False, "n_mc": 8},
        [table, meta],
    )
    np.testing.assert_allclose(out.data[:, 0], reference["diff"], rtol=1e-5, atol=1e-6)
    np.testing.assert_allclose(out.data[:, 2], reference["p"], rtol=1e-5, atol=1e-8)
