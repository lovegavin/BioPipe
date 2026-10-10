# src/task/step/steps/manhattan.py
"""Manhattan plot operator.

Input is a single 2D form. The operator draws a genome-wide scatter
of -log10(P) against cumulative genomic position.

Field locations
---------------
Each field is looked up either as a data column on a named dimension
or as an axis-parallel info entry. ``chrom_label`` and ``pos_label``
are looked up on ``dim``; ``p_label`` is looked up on ``p_dim``
(default: ``dim``). This lets chromosome/position come from one
dimension and the P value from another.

Chromosome values are kept as they appear (typically strings such as
``"22"``). They are grouped, ordered and labelled verbatim; no
encoding is applied.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._plot_helpers import save_figure, setup_style


class ManhattanStep(Step):
    """Draw a Manhattan plot.

    Params:
        dim         : observation dim (one point per position)
        chrom_label : chromosome field on ``dim``
        pos_label   : position field on ``dim``
        p_label     : P-value field
        p_dim       : dim carrying ``p_label`` (default: ``dim``)
        filename    : output file name
        threshold   : optional P threshold for a horizontal line
        title       : optional plot title
        point_size  : marker size (default 6)
        alpha       : marker transparency (default 0.85)
    """

    name = "manhattan"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        import matplotlib.pyplot as plt

        setup_style()

        form = inputs[0]
        dim = ctx.step_params.get("dim", "feature")
        chrom_label = ctx.step_params["chrom_label"]
        pos_label = ctx.step_params["pos_label"]
        p_label = ctx.step_params["p_label"]
        p_dim = ctx.step_params.get("p_dim", dim)
        filename = ctx.step_params["filename"]
        threshold = ctx.step_params.get("threshold")
        title = ctx.step_params.get("title")
        point_size = float(ctx.step_params.get("point_size", 6))
        alpha = float(ctx.step_params.get("alpha", 0.85))

        if form.data.ndim != 2:
            raise StepError(
                f"manhattan requires a 2D form, got ndim={form.data.ndim}"
            )
        if dim not in form.dims:
            raise StepError(
                f"Dim '{dim}' not present. Available: {form.dims}"
            )
        if p_dim not in form.dims:
            raise StepError(
                f"p_dim '{p_dim}' not present. Available: {form.dims}"
            )

        chrom_raw = self._resolve(form, chrom_label, dim, "chrom_label")
        pos_raw = self._resolve(form, pos_label, dim, "pos_label")
        p_raw = self._resolve(form, p_label, p_dim, "p_label")

        n_obs = form.data.shape[form.dims.index(dim)]
        for name, arr in (
            ("chrom_label", chrom_raw),
            ("pos_label", pos_raw),
            ("p_label", p_raw),
        ):
            if len(arr) != n_obs:
                raise StepError(
                    f"manhattan: {name} resolves to length {len(arr)} "
                    f"but dim '{dim}' has size {n_obs}"
                )

        pos = _as_numeric(pos_raw)
        p = np.asarray(p_raw, dtype=float)

        # Chromosome: keep as strings so tick labels stay readable.
        chrom = np.asarray(
            [str(v) for v in chrom_raw], dtype=object
        )

        valid = (
            np.isfinite(pos)
            & np.isfinite(p)
            & (p > 0)
            & (p <= 1)
            & (chrom != "")
            & (chrom != "None")
        )
        n_valid = int(valid.sum())
        if n_valid == 0:
            raise StepError("manhattan: no finite variants to plot")

        chrom = chrom[valid]
        pos = pos[valid].astype(np.int64)
        neglogp = -np.log10(p[valid])

        # Order chromosomes in a natural sort order: numeric if all
        # chrom values parse as integers, otherwise lexicographic.
        unique_chroms = _sort_chroms(chrom)

        # Cumulative x.
        cum_x = np.zeros(len(chrom), dtype=np.float64)
        ticks: list[float] = []
        tick_labels: list[str] = []
        cum = 0
        for c in unique_chroms:
            mask = chrom == c
            size = int(mask.sum())
            # Sort positions within chromosome.
            idx = np.where(mask)[0]
            order = np.argsort(pos[idx])
            cum_x[idx[order]] = np.arange(size) + cum
            ticks.append(cum + size / 2)
            tick_labels.append(str(c))
            cum += size

        fig, ax = plt.subplots(figsize=(11, 4))
        # Alternate colors by chromosome index.
        chrom_idx = np.array(
            [unique_chroms.index(c) for c in chrom]
        )
        colors = np.where(chrom_idx % 2 == 0, "#0072B2", "#D55E00")
        ax.scatter(
            cum_x, neglogp, c=colors, s=point_size, alpha=alpha,
            edgecolors="none", rasterized=True,
        )
        if threshold is not None:
            ax.axhline(
                -np.log10(threshold), color="#D62728",
                lw=0.9, ls="--",
                label=f"threshold P = {threshold:.1e}",
            )
            ax.legend(frameon=False, loc="upper right")

        ax.set_xlabel("Chromosome")
        ax.set_ylabel(r"$-\log_{10}(P)$")
        ax.set_xticks(ticks)
        ax.set_xticklabels(tick_labels, fontsize=7)
        if title:
            ax.set_title(title)

        out_path = save_figure(fig, ctx, filename)

        self._export_data = {
            "kind": "manhattan",
            "filename": filename,
            "path": out_path,
            "dim": dim,
            "p_dim": p_dim,
            "chrom_label": chrom_label,
            "pos_label": pos_label,
            "p_label": p_label,
            "threshold": threshold,
            "n_variants": n_valid,
            "chromosomes": [str(c) for c in unique_chroms],
        }

        ctx.metadata.setdefault(self.name, {})[filename] = {
            "n_variants": n_valid,
            "n_chromosomes": int(len(unique_chroms)),
            "path": out_path,
        }

        print(
            f"[manhattan] {n_valid} variants across "
            f"{len(unique_chroms)} chromosome(s) "
            f"({', '.join(tick_labels[:5])}"
            f"{'...' if len(tick_labels) > 5 else ''}) "
            f"-> {out_path}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data

    @staticmethod
    def _resolve(form: Form, label: str, dim: str, what: str):
        arr = form.get_parallel(label, dim)
        if arr is None:
            raise StepError(
                f"manhattan: {what}='{label}' is neither a data column "
                f"on '{dim}' nor an axis-parallel info entry on '{dim}'."
            )
        return np.asarray(arr)


def _as_numeric(arr: np.ndarray) -> np.ndarray:
    """Convert numeric-looking values to float; raise otherwise."""
    a = np.asarray(arr)
    if a.dtype.kind in ("i", "f"):
        return a.astype(float)
    try:
        return np.asarray([float(v) for v in a], dtype=float)
    except (ValueError, TypeError) as exc:
        raise StepError(
            f"manhattan: cannot convert values to numbers: {exc}"
        )


def _sort_chroms(chrom: np.ndarray) -> list[str]:
    """Return unique chromosome labels in natural order.

    Chromosomes are sorted numerically when every value parses as an
    integer, and lexicographically otherwise. This gives ``1, 2, ..., 22,
    X, Y`` for typical GRCh data and alphabet order for names like
    ``chr1, chr2``.
    """
    unique = list(dict.fromkeys(chrom.tolist()))
    try:
        return sorted(unique, key=lambda c: int(c))
    except (ValueError, TypeError):
        return sorted(unique)