# src/pipelines/gwas/plot.py
"""Publication-quality GWAS figures.

Each plot function is independent and defensive: a failure in one plot
never aborts the others. All functions write PNG files to the given
directory and return ``None``.

Style
-----
* Okabe-Ito colour-blind safe palette.
* Arial / Helvetica / DejaVu Sans fallback chain.
* 300 DPI, top/right spines removed, no frame legends.
* Rasterised scatter points to keep file size reasonable.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

# --------------------------------------------------------------------- #
# Global style
# --------------------------------------------------------------------- #

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


# --------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------- #

def _chrom_sort(df: pd.DataFrame) -> pd.DataFrame:
    """Sort a result frame by numeric chromosome then position."""
    df = df.dropna(subset=["P"]).copy()
    df["_cn"] = pd.to_numeric(
        df["CHROM"].astype(str).str.replace("chr", "", regex=False),
        errors="coerce",
    )
    return df.sort_values(
        ["_cn", "POS"], na_position="last"
    ).reset_index(drop=True)


def _cumulative_pos(df: pd.DataFrame):
    """Compute cumulative x positions and chromosome ticks."""
    chroms = df["_cn"].fillna(-1).astype(int).values
    unique = sorted(set(chroms))
    cum = 0
    cum_pos = np.zeros(len(df))
    ticks: list[float] = []
    labels: list[str] = []
    for c in unique:
        m = chroms == c
        size = int(m.sum())
        cum_pos[m] = np.arange(size) + cum
        ticks.append(cum + size / 2)
        labels.append(str(c) if c != -1 else "NA")
        cum += size
    return cum_pos, ticks, labels


# --------------------------------------------------------------------- #
# Plot functions
# --------------------------------------------------------------------- #

def plot_manhattan(
    results: pd.DataFrame,
    out_path,
    sig_threshold: float | None = None,
    top_n: int = 5,
) -> None:
    """Manhattan plot of -log10(P) by genomic position."""
    df = _chrom_sort(results)
    if df.empty:
        print("[plot] manhattan: no valid P values, skipped")
        return

    cum_pos, ticks, labels = _cumulative_pos(df)
    chroms = df["_cn"].fillna(-1).astype(int).values
    colors = np.where(chroms % 2 == 0, C_BLUE, C_VERM)
    neglogp = -np.log10(df["P"].values)

    fig, ax = plt.subplots(figsize=(11, 4))
    ax.scatter(
        cum_pos, neglogp, c=colors, s=6, alpha=0.85,
        edgecolors="none", rasterized=True,
    )
    if sig_threshold is not None:
        ax.axhline(
            -np.log10(sig_threshold), color=C_RED, lw=0.9, ls="--",
            label=f"Bonferroni $\\alpha$ = {sig_threshold:.2e}",
        )

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
    print(f"[plot] manhattan -> {out_path}")


def plot_qq(results: pd.DataFrame, out_path) -> None:
    """QQ plot of observed vs expected -log10(P) with lambda-GC."""
    df = results.dropna(subset=["P"])
    p = df["P"].values
    p = p[(p > 0) & (p <= 1)]
    if p.size == 0:
        print("[plot] qq: no valid P values, skipped")
        return

    p_sorted = np.sort(p)
    n = p_sorted.size
    expected = -np.log10((np.arange(1, n + 1) - 0.5) / n)
    observed = -np.log10(p_sorted)

    chi2 = stats.chi2.isf(p_sorted, df=1)
    lam = float(np.median(chi2) / CHI2_MEDIAN)

    fig, ax = plt.subplots(figsize=(4.2, 4.2))
    ax.scatter(
        expected, observed, s=8, color=C_BLUE,
        alpha=0.75, edgecolors="none", rasterized=True,
    )
    lim = max(expected.max(), observed.max()) * 1.05
    ax.plot([0, lim], [0, lim], color=C_RED, lw=0.8, ls="--")
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_xlabel(r"Expected $-\log_{10}(P)$")
    ax.set_ylabel(r"Observed $-\log_{10}(P)$")
    ax.text(
        0.05, 0.92, f"$\\lambda_{{GC}}$ = {lam:.3f}",
        transform=ax.transAxes, fontsize=10,
    )

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"[plot] qq -> {out_path}")


def plot_volcano(
    results: pd.DataFrame,
    out_path,
    sig_threshold: float | None = None,
) -> None:
    """Volcano plot of effect size vs significance."""
    df = results.dropna(subset=["P", "BETA"])
    if df.empty:
        print("[plot] volcano: no valid data, skipped")
        return

    x = df["BETA"].values
    y = -np.log10(df["P"].values)

    fig, ax = plt.subplots(figsize=(5, 4.5))
    if sig_threshold is not None:
        sig = df["P"].values < sig_threshold
        ax.scatter(
            x[~sig], y[~sig], s=8, color=C_GREY,
            alpha=0.6, edgecolors="none", rasterized=True,
        )
        ax.scatter(
            x[sig], y[sig], s=12, color=C_RED,
            alpha=0.9, edgecolors="none", rasterized=True,
        )
        ax.axhline(
            -np.log10(sig_threshold), color=C_RED, lw=0.8, ls="--"
        )
    else:
        ax.scatter(
            x, y, s=8, color=C_BLUE,
            alpha=0.7, edgecolors="none", rasterized=True,
        )

    ax.axvline(0, color="#888888", lw=0.5, ls=":")
    ax.set_xlabel(r"Effect size ($\beta$)")
    ax.set_ylabel(r"$-\log_{10}(P)$")

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"[plot] volcano -> {out_path}")


def plot_forest(
    results: pd.DataFrame,
    out_path,
    top_n: int = 20,
) -> None:
    """Forest plot of top-N variants with 95% confidence intervals."""
    df = results.dropna(subset=["BETA", "SE", "P"])
    if df.empty:
        print("[plot] forest: no valid data, skipped")
        return

    df = df.nsmallest(top_n, "P").iloc[::-1].reset_index(drop=True)

    fig, ax = plt.subplots(figsize=(5.5, max(3, 0.28 * len(df))))
    y_pos = np.arange(len(df))
    ax.errorbar(
        df["BETA"], y_pos, xerr=1.96 * df["SE"],
        fmt="o", color=C_BLUE, ecolor="#555555",
        markersize=4, capsize=2, lw=0.8,
    )
    ax.axvline(0, color=C_RED, lw=0.8, ls="--")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(df["ID"], fontsize=8)
    ax.set_xlabel(r"Effect size ($\beta$ with 95% CI)")
    ax.set_ylabel("Variant")

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"[plot] forest -> {out_path}")


def plot_maf_distribution(
    results: pd.DataFrame,
    out_path,
    bins: int = 40,
) -> None:
    """Histogram of minor allele frequencies."""
    df = results.dropna(subset=["MAF"])
    if df.empty:
        print("[plot] maf_distribution: no MAF values, skipped")
        return

    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    ax.hist(
        df["MAF"], bins=bins, color=C_BLUE,
        edgecolor="white", linewidth=0.4,
    )
    ax.set_xlabel("Minor allele frequency (MAF)")
    ax.set_ylabel("Number of variants")

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"[plot] maf_distribution -> {out_path}")


def plot_pvalue_histogram(
    results: pd.DataFrame,
    out_path,
    bins: int = 50,
) -> None:
    """Histogram of P values against the uniform expectation."""
    df = results.dropna(subset=["P"])
    if df.empty:
        print("[plot] pvalue_histogram: no P values, skipped")
        return

    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    ax.hist(
        df["P"], bins=bins, range=(0, 1), density=True,
        color=C_BLUE, edgecolor="white", linewidth=0.4, label="Observed",
    )
    ax.axhline(
        1.0, color=C_RED, lw=0.9, ls="--", label="Expected (uniform)"
    )
    ax.set_xlabel("$P$ value")
    ax.set_ylabel("Density")
    ax.legend(frameon=False)

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"[plot] pvalue_histogram -> {out_path}")


def plot_chromosome_density(results: pd.DataFrame, out_path) -> None:
    """Number of tested variants per chromosome."""
    df = results.copy()
    df["_cn"] = pd.to_numeric(
        df["CHROM"].astype(str).str.replace("chr", "", regex=False),
        errors="coerce",
    )
    df = df.dropna(subset=["_cn"])
    if df.empty:
        print("[plot] chromosome_density: no valid chromosomes, skipped")
        return

    counts = df.groupby("_cn").size().sort_index()
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.bar(
        counts.index.astype(int).astype(str), counts.values,
        color=C_BLUE, edgecolor="white", linewidth=0.4,
    )
    ax.set_xlabel("Chromosome")
    ax.set_ylabel("Number of variants")
    plt.setp(ax.get_xticklabels(), rotation=0, fontsize=7)

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"[plot] chromosome_density -> {out_path}")


def plot_effect_vs_maf(
    results: pd.DataFrame,
    out_path,
    sig_threshold: float | None = None,
) -> None:
    """Effect size against minor allele frequency."""
    df = results.dropna(subset=["BETA", "MAF"])
    if df.empty:
        print("[plot] effect_vs_maf: no valid data, skipped")
        return

    fig, ax = plt.subplots(figsize=(4.8, 3.6))
    if sig_threshold is not None:
        sig = df["P"].values < sig_threshold
        ax.scatter(
            df["MAF"][~sig], df["BETA"][~sig],
            s=6, color=C_GREY, alpha=0.55,
            edgecolors="none", rasterized=True,
        )
        ax.scatter(
            df["MAF"][sig], df["BETA"][sig],
            s=12, color=C_RED, alpha=0.9,
            edgecolors="none", rasterized=True, label="Significant",
        )
        ax.legend(frameon=False)
    else:
        ax.scatter(
            df["MAF"], df["BETA"], s=6, color=C_BLUE,
            alpha=0.65, edgecolors="none", rasterized=True,
        )

    ax.axhline(0, color="#888888", lw=0.5, ls=":")
    ax.set_xlabel("Minor allele frequency (MAF)")
    ax.set_ylabel(r"Effect size ($\beta$)")

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"[plot] effect_vs_maf -> {out_path}")


def plot_pca_scatter(
    pcs: np.ndarray,
    explained_var: np.ndarray,
    out_path,
) -> None:
    """Scatter plot of PC1 vs PC2."""
    if pcs is None or pcs.shape[1] < 2:
        return

    fig, ax = plt.subplots(figsize=(4.5, 4.0))
    ax.scatter(
        pcs[:, 0], pcs[:, 1], s=14,
        color=C_BLUE, alpha=0.85, edgecolors="none",
    )
    ax.set_xlabel(f"PC1 ({explained_var[0] * 100:.2f}%)")
    ax.set_ylabel(f"PC2 ({explained_var[1] * 100:.2f}%)")

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"[plot] pca_scatter -> {out_path}")


def plot_pca_scree(explained_var: np.ndarray, out_path) -> None:
    """Bar chart of per-component explained variance."""
    if explained_var is None or explained_var.size == 0:
        return

    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    n = explained_var.size
    ax.bar(
        np.arange(1, n + 1), explained_var * 100,
        color=C_BLUE, edgecolor="white", linewidth=0.4,
    )
    ax.set_xlabel("Principal component")
    ax.set_ylabel("Explained variance (%)")
    ax.set_xticks(np.arange(1, n + 1))
    ax.set_xticklabels(np.arange(1, n + 1), fontsize=8)

    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    print(f"[plot] pca_scree -> {out_path}")


# --------------------------------------------------------------------- #
# Dispatcher
# --------------------------------------------------------------------- #

def plot_all(
    results: pd.DataFrame,
    out_dir,
    config: dict,
    sig_threshold: float | None = None,
    pcs: np.ndarray | None = None,
    explained_var: np.ndarray | None = None,
) -> None:
    """Render every figure enabled in ``config['plots']``.

    Parameters
    ----------
    results : pd.DataFrame
        The association result table.
    out_dir : path-like
        Directory for output PNG files. Created if missing.
    config : dict
        Full manifest. Only ``config['plots']`` is read.
    sig_threshold : float, optional
        P-value threshold drawn on Manhattan and volcano plots.
    pcs : np.ndarray, optional
        Sample x component PCA scores, for the scatter plot.
    explained_var : np.ndarray, optional
        Per-component explained variance ratios.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plots = config.get("plots", {})

    # Every call is isolated; a failure does not stop the others.
    for key, fn, kwargs in (
        ("manhattan", plot_manhattan,
            {"sig_threshold": sig_threshold}),
        ("qq", plot_qq, {}),
        ("volcano", plot_volcano,
            {"sig_threshold": sig_threshold}),
        ("forest", plot_forest,
            {"top_n": int(plots.get("top_n_forest", 20))}),
        ("maf_distribution", plot_maf_distribution, {}),
        ("pvalue_histogram", plot_pvalue_histogram, {}),
        ("chromosome_density", plot_chromosome_density, {}),
        ("effect_vs_maf", plot_effect_vs_maf,
            {"sig_threshold": sig_threshold}),
    ):
        if not plots.get(key, True):
            continue
        try:
            fn(results, out_dir / f"{key}.png", **kwargs)
        except Exception as exc:
            print(f"[plot] {key} failed: {exc}")

    # PCA plots require additional artefacts.
    if pcs is not None and explained_var is not None:
        if plots.get("pca_scatter", True):
            try:
                plot_pca_scatter(
                    pcs, explained_var, out_dir / "pca_scatter.png"
                )
            except Exception as exc:
                print(f"[plot] pca_scatter failed: {exc}")
        if plots.get("pca_scree", True):
            try:
                plot_pca_scree(
                    explained_var, out_dir / "pca_scree.png"
                )
            except Exception as exc:
                print(f"[plot] pca_scree failed: {exc}")