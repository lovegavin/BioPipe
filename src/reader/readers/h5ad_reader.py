# src/reader/readers/h5ad_reader.py
"""H5AD reader (AnnData).

Reads the main expression matrix and its two axes' identifiers from
an .h5ad file.

Layout:
    axis 0 = cell, axis 1 = gene.
``dims`` names the two axes in that order.

The matrix is read from ``adata.X``. If it is sparse, it is densified.
Cell and gene identifiers come from ``adata.obs.index`` and
``adata.var.index``.

Backed by anndata.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.reader.base import Reader


class H5adReader(Reader):
    """Reader for .h5ad files."""

    extensions = [".h5ad"]

    def read(self, path: Path, dims, labels, **args) -> Form:
        if not isinstance(dims, list) or len(dims) != 2:
            raise ReaderError(
                "H5AD reader expects dims as a two-element list, "
                "e.g. dims: [cell, gene]"
            )
        cell_dim, gene_dim = dims[0], dims[1]

        try:
            import anndata as ad
            from scipy.sparse import issparse
        except ImportError as exc:
            raise ReaderError(
                "anndata and scipy are required to read .h5ad files. "
                "Install with: pip install anndata scipy"
            ) from exc

        adata = ad.read_h5ad(str(path))

        X = adata.X
        if X is None:
            raise ReaderError(
                f"H5AD file has no X matrix: {path}"
            )

        if issparse(X):
            X = X.toarray()

        data = np.asarray(X, dtype=np.float32)

        cell_ids = [str(c) for c in adata.obs.index]
        gene_ids = [str(g) for g in adata.var.index]

        n_cells, n_genes = data.shape
        if len(cell_ids) != n_cells:
            raise ReaderError(
                f"obs has {len(cell_ids)} rows but X has {n_cells}"
            )
        if len(gene_ids) != n_genes:
            raise ReaderError(
                f"var has {len(gene_ids)} rows but X has {n_genes}"
            )

        return Form(
            data=data,
            dims=[cell_dim, gene_dim],
            labels={
                cell_dim: {c: i for i, c in enumerate(cell_ids)},
                gene_dim: {g: i for i, g in enumerate(gene_ids)},
            },
            info={"missing_code": np.nan},
        )