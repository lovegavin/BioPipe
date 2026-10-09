# src/reader/readers/mtx_reader.py
"""MatrixMarket MTX reader (10x Genomics MEX format).

Reads a MEX triplet:
    matrix.mtx.gz    — sparse count matrix (gene x cell)
    barcodes.tsv.gz  — cell barcodes (columns)
    features.tsv.gz  — gene features (rows)

Per the 10x Genomics documentation, each element of the matrix is the
number of UMIs associated with a feature (row) and a barcode (column).
Genes are rows; cells are columns.

MatrixMarket coordinate format uses 1-based indexing. The header line
is ``%%MatrixMarket matrix coordinate real general`` followed by
``m n nnz`` where m is the number of rows and n the number of columns.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import mmread

from src.core import Form, ReaderError
from src.reader.base import Reader


class MtxReader(Reader):
    """Reader for MatrixMarket .mtx / .mtx.gz files."""

    extensions = [".mtx"]

    def read(self, path: Path, dims, labels, **args) -> Form:
        if not isinstance(dims, list) or len(dims) != 2:
            raise ReaderError(
                "MTX reader expects dims as a two-element list, "
                "e.g. dims: [gene, cell]"
            )
        gene_dim, cell_dim = dims[0], dims[1]

        path = Path(path)
        parent = path.parent

        barcodes_path = _find_sibling(parent, "barcodes.tsv")
        features_path = _find_sibling(parent, "features.tsv")
        if barcodes_path is None or features_path is None:
            features_path = _find_sibling(parent, "genes.tsv")
            if features_path is None:
                raise ReaderError(
                    f"Cannot find barcodes.tsv(.gz) or features.tsv(.gz) "
                    f"next to {path}"
                )

        with _open_maybe_gz(path) as fh:
            matrix = mmread(fh)
        matrix = matrix.tocsr()
        n_genes, n_cells = matrix.shape

        barcodes = _read_tsv_column(barcodes_path, col=0)
        if len(barcodes) != n_cells:
            raise ReaderError(
                f"barcodes has {len(barcodes)} rows but matrix has "
                f"{n_cells} columns"
            )

        features_df = _read_tsv(features_path)
        if features_df.shape[0] != n_genes:
            raise ReaderError(
                f"features has {features_df.shape[0]} rows but matrix has "
                f"{n_genes} rows"
            )
        gene_ids = features_df.iloc[:, 0].astype(str).tolist()

        data = matrix.toarray().astype(np.float32)

        return Form(
            data=data,
            dims=[gene_dim, cell_dim],
            labels={
                gene_dim: {g: i for i, g in enumerate(gene_ids)},
                cell_dim: {b: i for i, b in enumerate(barcodes)},
            },
            info={"missing_code": np.nan},
        )


def _open_maybe_gz(path: Path):
    if str(path).lower().endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def _find_sibling(parent: Path, stem: str) -> Path | None:
    for name in (stem, stem + ".gz"):
        p = parent / name
        if p.exists():
            return p
    return None


def _read_tsv(path: Path) -> pd.DataFrame:
    with _open_maybe_gz(path) as fh:
        return pd.read_csv(fh, sep="\t", header=None)


def _read_tsv_column(path: Path, col: int) -> list[str]:
    with _open_maybe_gz(path) as fh:
        values = []
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if col < len(parts):
                values.append(parts[col])
    return values