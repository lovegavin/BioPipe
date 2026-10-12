# src/task/step/steps/heatmap.py
"""Heatmap of a 2D form.

Renders the matrix as an image with one cell per position. Rows and
columns can be reordered by hierarchical clustering, and rows can be
standardized before plotting.

Row selection
-------------
    select="variance"   pick the top ``top_n`` rows by variance
                        (default)
    select="label"      pick the rows named in ``labels``
    select="all"        keep all rows

Standardization
---------------
    standardize="row"   z-score each row (mean 0, std 1)
    standardize="col"   z-score each column
    standardize="none"  no transformation (default)

Missing values are shown as the ``nan_color``.

Params:
    dim          : feature dim (default "feature")
    other_dim    : sample dim (default "sample")
    select       : "variance" | "label" | "all"
    top_n        : number of rows when select="variance" (default 50)
    labels       : list of row labels when select="label"
    standardize  : "row" | "col" | "none"
    cluster_rows : hierarchical clustering of rows (default True)
    cluster_cols : hierarchical clustering of columns (default True)
    filename     : output file name (required)
    title        : optional plot title
    cmap         : matplotlib colormap (default "RdBu_r")
    nan_color    : color for missing cells (default "#DDDDDD")
    figsize      : [width, height] in inches (default auto)
    show_row_labels   : show row tick labels (default False)
    show_col_labels   : show column tick labels (default True)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.core.contracts import port, param
from src.core.forms.metadata import project_metadata
from src.task.step.steps._plot_helpers import save_figure, setup_style


class HeatmapStep(Step):
    """Draw a heatmap of a 2D form."""

    name = "heatmap"
    inputs_arity = 1
    outputs = []
    input_contracts = [port(ndim=2, dims=[param("dim", "feature"), param("other_dim", "sample")])]
    output_contract = {"mode": "none"}

    def run(self, ctx: Context, inputs) -> None:
        import matplotlib.pyplot as plt

        setup_style()

        form = inputs[0]
        dim = ctx.step_params.get("dim", "feature")
        other_dim = ctx.step_params.get("other_dim", "sample")
        select = ctx.step_params.get("select", "variance")
        top_n = int(ctx.step_params.get("top_n", 50))
        labels_list = ctx.step_params.get("labels")
        standardize = ctx.step_params.get("standardize", "none")
        cluster_rows = bool(ctx.step_params.get("cluster_rows", True))
        cluster_cols = bool(ctx.step_params.get("cluster_cols", True))
        filename = ctx.step_params.get("filename")
        title = ctx.step_params.get("title")
        cmap = ctx.step_params.get("cmap", "RdBu_r")
        nan_color = ctx.step_params.get("nan_color", "#DDDDDD")
        figsize = ctx.step_params.get("figsize")
        show_row_labels = bool(
            ctx.step_params.get("show_row_labels", False)
        )
        show_col_labels = bool(
            ctx.step_params.get("show_col_labels", True)
        )

        if not filename:
            raise StepError("heatmap: 'filename' is required")
        if form.data.ndim != 2:
            raise StepError(
                f"heatmap: input must be 2D, got ndim={form.data.ndim}"
            )
        for d, name in ((dim, "dim"), (other_dim, "other_dim")):
            if d not in form.dims:
                raise StepError(
                    f"heatmap: {name} '{d}' not present. "
                    f"Available: {form.dims}"
                )
        if dim == other_dim:
            raise StepError(
                f"heatmap: dim and other_dim are both '{dim}'"
            )
        if select not in ("variance", "label", "all"):
            raise StepError(
                f"heatmap: select must be 'variance', 'label' or "
                f"'all', got {select!r}"
            )
        if standardize not in ("row", "col", "none"):
            raise StepError(
                f"heatmap: standardize must be 'row', 'col' or "
                f"'none', got {standardize!r}"
            )
        if select == "label" and not labels_list:
            raise StepError(
                "heatmap: select='label' requires 'labels'"
            )
        if top_n < 1:
            raise StepError(
                f"heatmap: top_n must be >= 1, got {top_n}"
            )

        # Orient so that rows = dim, cols = other_dim.
        feat_axis = form.dims.index(dim)
        other_axis = form.dims.index(other_dim)
        matrix = np.moveaxis(form.data, (feat_axis, other_axis), (0, 1))
        matrix = matrix.astype(np.float64)

        row_labels_map = form.labels[dim]
        col_labels_map = form.labels[other_dim]
        row_pos_to_label = {v: k for k, v in row_labels_map.items()}
        col_pos_to_label = {v: k for k, v in col_labels_map.items()}

        row_names_all = [
            row_pos_to_label[i] for i in range(matrix.shape[0])
        ]
        col_names_all = [
            col_pos_to_label[i] for i in range(matrix.shape[1])
        ]

        # Row selection
        if select == "variance":
            with np.errstate(invalid="ignore"):
                var = np.nanvar(matrix, axis=1)
            var = np.where(np.isfinite(var), var, -np.inf)
            order = np.argsort(var)[::-1]
            row_idx = order[:top_n]
        elif select == "label":
            missing = [l for l in labels_list if l not in row_labels_map]
            if missing:
                raise StepError(
                    f"heatmap: labels not found in dim '{dim}': "
                    f"{missing[:5]}"
                )
            row_idx = np.array(
                [row_labels_map[l] for l in labels_list], dtype=int
            )
        else:  # all
            row_idx = np.arange(matrix.shape[0])

        matrix = matrix[row_idx, :]
        row_names = [row_names_all[i] for i in row_idx]
        col_names = col_names_all

        if matrix.size == 0:
            raise StepError("heatmap: selected matrix is empty")

        # Standardization
        if standardize == "row":
            with np.errstate(invalid="ignore"):
                mu = np.nanmean(matrix, axis=1, keepdims=True)
                sd = np.nanstd(matrix, axis=1, keepdims=True)
            sd = np.where(sd > 1e-12, sd, 1.0)
            matrix = (matrix - mu) / sd
        elif standardize == "col":
            with np.errstate(invalid="ignore"):
                mu = np.nanmean(matrix, axis=0, keepdims=True)
                sd = np.nanstd(matrix, axis=0, keepdims=True)
            sd = np.where(sd > 1e-12, sd, 1.0)
            matrix = (matrix - mu) / sd

        # Clustering order
        row_order = np.arange(matrix.shape[0])
        col_order = np.arange(matrix.shape[1])

        if cluster_rows and matrix.shape[0] > 1:
            row_order = _cluster_order(matrix)
        if cluster_cols and matrix.shape[1] > 1:
            col_order = _cluster_order(matrix.T)

        matrix = matrix[row_order, :][:, col_order]
        row_names = [row_names[i] for i in row_order]
        col_names = [col_names[i] for i in col_order]

        finite = matrix[np.isfinite(matrix)]
        if finite.size == 0:
            raise StepError(
                "heatmap: no finite values in the selected matrix"
            )

        vmin = float(np.quantile(finite, 0.02))
        vmax = float(np.quantile(finite, 0.98))
        if vmin == vmax:
            vmin, vmax = float(finite.min()), float(finite.max())
            if vmin == vmax:
                vmin, vmax = vmin - 0.5, vmax + 0.5

        cmap_obj = plt.get_cmap(cmap).copy()
        cmap_obj.set_bad(nan_color)

        if figsize is None:
            w = max(3.5, 0.18 * matrix.shape[1] + 1.5)
            h = max(3.0, 0.12 * matrix.shape[0] + 1.5)
            figsize = [w, h]

        fig, ax = plt.subplots(figsize=tuple(figsize))
        im = ax.imshow(
            matrix, aspect="auto", cmap=cmap_obj,
            vmin=vmin, vmax=vmax, interpolation="nearest",
        )

        ax.set_xticks(np.arange(matrix.shape[1]))
        if show_col_labels:
            ax.set_xticklabels(
                col_names, rotation=90, fontsize=7,
            )
        else:
            ax.set_xticklabels([])

        if show_row_labels:
            ax.set_yticks(np.arange(matrix.shape[0]))
            ax.set_yticklabels(row_names, fontsize=6)
        else:
            ax.set_yticks([])

        ax.set_xlabel(other_dim)
        ax.set_ylabel(dim)
        if title:
            ax.set_title(title)

        cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
        if standardize == "row":
            cbar.set_label(f"{dim} z-score")
        elif standardize == "col":
            cbar.set_label(f"{other_dim} z-score")
        else:
            cbar.set_label("value")

        out_path = save_figure(fig, ctx, filename)

        self._export_data = {
            "kind": "heatmap",
            "filename": filename,
            "path": out_path,
            "dim": dim,
            "other_dim": other_dim,
            "select": select,
            "top_n": top_n if select == "variance" else None,
            "standardize": standardize,
            "cluster_rows": cluster_rows,
            "cluster_cols": cluster_cols,
            "n_rows": int(matrix.shape[0]),
            "n_cols": int(matrix.shape[1]),
            "vmin": vmin,
            "vmax": vmax,
            "row_order": [row_names[i] for i in range(matrix.shape[0])],
            "col_order": [col_names[i] for i in range(matrix.shape[1])],
        }

        ctx.metadata.setdefault(self.name, {})[filename] = {
            "n_rows": int(matrix.shape[0]),
            "n_cols": int(matrix.shape[1]),
            "path": out_path,
        }

        print(
            f"[heatmap] {matrix.shape[0]} x {matrix.shape[1]} "
            f"(select={select}, standardize={standardize}, "
            f"cluster_rows={cluster_rows}, cluster_cols={cluster_cols}) "
            f"-> {out_path}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _cluster_order(matrix: np.ndarray) -> np.ndarray:
    """Return a leaf order from hierarchical clustering.

    Fills NaN with 0 for the distance computation, since scipy's
    linkage cannot handle NaN.
    """
    from scipy.cluster.hierarchy import leaves_list, linkage

    filled = np.where(np.isfinite(matrix), matrix, 0.0)
    if filled.shape[0] < 2:
        return np.arange(filled.shape[0])
    link = linkage(filled, method="average")
    return leaves_list(link).astype(int)