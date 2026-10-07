# src/pipelines/gwas/plot.py
"""论文级 GWAS 可视化"""

from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

# ---------- 论文规范全局设置 ----------
matplotlib.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 12,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "axes.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "xtick.major.size": 3,
    "ytick.major.size": 3,
    "lines.linewidth": 1.0,
    "figure.dpi": 100,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.1,
})

C_BLUE = "#0072B2"
C_VERM = "#D55E00"
C_GREEN = "#009E73"
C_PINK = "#CC79A7"
C_RED = "#D62728"
C_GREY = "#7F7F7F"

CHI2_MEDIAN = 0.4549364


# ---------- 通用工具 ----------
def _chrom_sort(df):
    df = df.dropna(subset=["P"]).copy()
    df["_cn"] = pd.to_numeric(
        df["CHROM"].astype(str).str.replace("chr", "", regex=False),
        errors="coerce",
    )
    return df.sort_values(["_cn", "POS"], na_position="last").reset_index(drop=True)


def _cumulative_pos(df):
    chroms = df["_cn"].fillna(-1).astype(int).values
    unique = sorted(set(chroms))
    cum = 0
    cum_pos = np.zeros(len(df))
    ticks, labels = [], []
    for c in unique:
        m = chroms == c
        size = int(m.sum())
        cum_pos[m] = np.arange(size) + cum
        ticks.append(cum + size / 2)
        labels.append(str(c) if c != -1 else "NA")
        cum += size
    return cum_pos, ticks, labels


# ---------- 各图 ----------
def plot_manhattan(results, out_path, sig_threshold=None, top_n=5):
    df = _chrom_sort(results)
    if df.empty:
        print("曼哈顿图: 无有效 P 值, 跳过")
        return
    cum_pos, ticks, labels = _cumulative_pos(df)
    chroms = df["_cn"].fillna(-1).astype(int).values
    colors = np.where(chroms % 2 == 0, C_BLUE, C_VERM)
    neglogp = -np.log10(df["P"].values)

    fig, ax = plt.subplots(figsize=(11, 4))
    ax.scatter(cum_pos, neglogp, c=colors, s=6,
               alpha=0.85, edgecolors="none", rasterized=True)
    if sig_threshold is not None:
        ax.axhline(-np.log10(sig_threshold), color=C_RED, lw=0.9, ls="--",
                   label=f"Bonferroni $\\alpha$ = {sig_threshold:.2e}")
    top_idx = df["P"].nsmallest(top_n).index
    for i in top_idx:
        ax.annotate(
            df.loc[i, "ID"],
            xy=(cum_pos[i], neglogp[i]),
            xytext=(cum_pos[i], neglogp[i] + 0.8),
            fontsize=7, ha="center", color="#333333",
            arrowprops=dict(arrowstyle="-", lw=0.5, color="#666666"),
        )
    ax.set_xlabel("Chromosome")
    ax.set_ylabel(r"$-\log_{10}(P)$")
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_xlim(-1, cum_pos.max() + 1)
    if sig_threshold is not None:
        ax.legend(loc="upper right", frameon=False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"曼哈顿图: {out_path}")


def plot_qq(results, out_path):
    df = results.dropna(subset=["P"])
    p = df["P"].values
    p = p[(p > 0) & (p <= 1)]
    if p.size == 0:
        print("QQ图: 无有效 P 值, 跳过")
        return
    p_sorted = np.sort(p)
    n = p_sorted.size
    expected = -np.log10((np.arange(1, n + 1) - 0.5) / n)
    observed = -np.log10(p_sorted)

    chi2 = stats.chi2.isf(p_sorted, df=1)
    lam = float(np.median(chi2) / CHI2_MEDIAN)

    fig, ax = plt.subplots(figsize=(4.2, 4.2))
    ax.scatter(expected, observed, s=8, color=C_BLUE,
               alpha=0.75, edgecolors="none", rasterized=True)
    lim = max(expected.max(), observed.max()) * 1.05
    ax.plot([0, lim], [0, lim], color=C_RED, lw=0.8, ls="--")
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_xlabel(r"Expected $-\log_{10}(P)$")
    ax.set_ylabel(r"Observed $-\log_{10}(P)$")
    ax.text(0.05, 0.92, f"$\\lambda_{{GC}}$ = {lam:.3f}",
            transform=ax.transAxes, fontsize=10)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"QQ图: {out_path}")


def plot_volcano(results, out_path, sig_threshold=None):
    df = results.dropna(subset=["P", "BETA"])
    if df.empty:
        print("火山图: 无有效数据, 跳过")
        return
    x = df["BETA"].values
    y = -np.log10(df["P"].values)

    fig, ax = plt.subplots(figsize=(5, 4.5))
    if sig_threshold is not None:
        sig = df["P"].values < sig_threshold
        ax.scatter(x[~sig], y[~sig], s=8, color=C_GREY,
                   alpha=0.6, edgecolors="none", rasterized=True)
        ax.scatter(x[sig], y[sig], s=12, color=C_RED,
                   alpha=0.9, edgecolors="none", rasterized=True)
        ax.axhline(-np.log10(sig_threshold), color=C_RED, lw=0.8, ls="--")
    else:
        ax.scatter(x, y, s=8, color=C_BLUE,
                   alpha=0.7, edgecolors="none", rasterized=True)
    ax.axvline(0, color="#888888", lw=0.5, ls=":")
    ax.set_xlabel(r"Effect size ($\beta$)")
    ax.set_ylabel(r"$-\log_{10}(P)$")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"火山图: {out_path}")


def plot_forest(results, out_path, top_n=20):
    df = results.dropna(subset=["BETA", "SE", "P"])
    if df.empty:
        print("森林图: 无有效数据, 跳过")
        return
    df = df.nsmallest(top_n, "P").iloc[::-1].reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(5.5, max(3, 0.28 * len(df))))
    y_pos = np.arange(len(df))
    ax.errorbar(df["BETA"], y_pos, xerr=1.96 * df["SE"],
                fmt="o", color=C_BLUE, ecolor="#555555",
                markersize=4, capsize=2, lw=0.8)
    ax.axvline(0, color=C_RED, lw=0.8, ls="--")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(df["ID"], fontsize=8)
    ax.set_xlabel(r"Effect size ($\beta$ with 95% CI)")
    ax.set_ylabel("Variant")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"森林图: {out_path}")


def plot_maf_distribution(results, out_path, bins=40):
    df = results.dropna(subset=["MAF"])
    if df.empty:
        return
    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    ax.hist(df["MAF"], bins=bins, color=C_BLUE,
            edgecolor="white", linewidth=0.4)
    ax.set_xlabel("Minor allele frequency (MAF)")
    ax.set_ylabel("Number of variants")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"MAF 分布: {out_path}")


def plot_pvalue_histogram(results, out_path, bins=50):
    df = results.dropna(subset=["P"])
    if df.empty:
        return
    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    ax.hist(df["P"], bins=bins, range=(0, 1), density=True,
            color=C_BLUE, edgecolor="white", linewidth=0.4, label="Observed")
    ax.axhline(1.0, color=C_RED, lw=0.9, ls="--", label="Expected (uniform)")
    ax.set_xlabel("$P$ value")
    ax.set_ylabel("Density")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"P 值分布: {out_path}")


def plot_chromosome_density(results, out_path):
    df = results.copy()
    df["_cn"] = pd.to_numeric(
        df["CHROM"].astype(str).str.replace("chr", "", regex=False),
        errors="coerce",
    )
    df = df.dropna(subset=["_cn"])
    if df.empty:
        return
    counts = df.groupby("_cn").size().sort_index()
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.bar(counts.index.astype(int).astype(str), counts.values,
           color=C_BLUE, edgecolor="white", linewidth=0.4)
    ax.set_xlabel("Chromosome")
    ax.set_ylabel("Number of variants")
    plt.setp(ax.get_xticklabels(), rotation=0, fontsize=7)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"染色体密度: {out_path}")


def plot_effect_vs_maf(results, out_path, sig_threshold=None):
    df = results.dropna(subset=["BETA", "MAF"])
    if df.empty:
        return
    fig, ax = plt.subplots(figsize=(4.8, 3.6))
    if sig_threshold is not None:
        sig = df["P"].values < sig_threshold
        ax.scatter(df["MAF"][~sig], df["BETA"][~sig],
                   s=6, color=C_GREY, alpha=0.55,
                   edgecolors="none", rasterized=True)
        ax.scatter(df["MAF"][sig], df["BETA"][sig],
                   s=12, color=C_RED, alpha=0.9,
                   edgecolors="none", rasterized=True, label="Significant")
        ax.legend(frameon=False)
    else:
        ax.scatter(df["MAF"], df["BETA"], s=6, color=C_BLUE,
                   alpha=0.65, edgecolors="none", rasterized=True)
    ax.axhline(0, color="#888888", lw=0.5, ls=":")
    ax.set_xlabel("Minor allele frequency (MAF)")
    ax.set_ylabel(r"Effect size ($\beta$)")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"Effect-MAF: {out_path}")


def plot_pca_scatter(pcs, explained_var, out_path, labels=None):
    if pcs.shape[1] < 2:
        return
    fig, ax = plt.subplots(figsize=(4.5, 4.0))
    if labels is not None:
        uniq = sorted(set(labels))
        palette = [C_BLUE, C_VERM, C_GREEN, C_PINK, C_RED, C_GREY]
        for k, lab in enumerate(uniq):
            m = np.array(labels) == lab
            ax.scatter(pcs[m, 0], pcs[m, 1], s=14,
                       color=palette[k % len(palette)],
                       alpha=0.85, edgecolors="none", label=str(lab))
        ax.legend(frameon=False)
    else:
        ax.scatter(pcs[:, 0], pcs[:, 1], s=14,
                   color=C_BLUE, alpha=0.85, edgecolors="none")
    ax.set_xlabel(f"PC1 ({explained_var[0]*100:.2f}%)")
    ax.set_ylabel(f"PC2 ({explained_var[1]*100:.2f}%)")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"PCA 散点: {out_path}")


def plot_pca_scree(explained_var, out_path):
    if explained_var.size == 0:
        return
    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    n = explained_var.size
    ax.bar(np.arange(1, n + 1), explained_var * 100,
           color=C_BLUE, edgecolor="white", linewidth=0.4)
    ax.set_xlabel("Principal component")
    ax.set_ylabel("Explained variance (%)")
    ax.set_xticks(np.arange(1, n + 1))
    ax.set_xticklabels(np.arange(1, n + 1), fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"PCA 碎石图: {out_path}")


def plot_all(results, out_dir, config, sig_threshold=None,
             pcs=None, explained_var=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plots = config.get("plots", {})

    if plots.get("manhattan", True):
        plot_manhattan(results, out_dir / "manhattan.png", sig_threshold)
    if plots.get("qq", True):
        plot_qq(results, out_dir / "qq.png")
    if plots.get("volcano", True):
        plot_volcano(results, out_dir / "volcano.png", sig_threshold)
    if plots.get("forest", True):
        plot_forest(results, out_dir / "forest.png",
                    int(plots.get("top_n_forest", 20)))
    if plots.get("maf_distribution", True):
        plot_maf_distribution(results, out_dir / "maf_distribution.png")
    if plots.get("pvalue_histogram", True):
        plot_pvalue_histogram(results, out_dir / "pvalue_histogram.png")
    if plots.get("chromosome_density", True):
        plot_chromosome_density(results, out_dir / "chromosome_density.png")
    if plots.get("effect_vs_maf", True):
        plot_effect_vs_maf(results, out_dir / "effect_vs_maf.png",
                           sig_threshold)
    if pcs is not None and explained_var is not None:
        if plots.get("pca_scatter", True):
            plot_pca_scatter(pcs, explained_var,
                             out_dir / "pca_scatter.png")
        if plots.get("pca_scree", True):
            plot_pca_scree(explained_var, out_dir / "pca_scree.png")