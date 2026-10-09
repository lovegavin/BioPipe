# src/reader/readers/mtx_reader.py
"""MatrixMarket MTX reader (10x Genomics MEX format).

Reads a MEX triplet:
    matrix.mtx.gz    — sparse count matrix (gene x cell)
    barcodes.tsv.gz  — cell barcodes (columns)
    features.tsv.gz  — gene features (rows)

The three files must live in the same directory. The reader is
triggered by pointing at the .mtx.gz file; it locates the sibling
barcodes and features files automatically.

Layout is the natural 10x order:
    axis 0 = gene, axis 1 = cell.
``dims`` names the two axes in that order.

Labels come from the files:
    gene axis — the gene ID column of features.tsv.gz
    cell axis — the barcode column of barcodes.tsv.gz
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

        # Locate sibling barcodes and features files. Accept both .gz
        # and uncompressed variants.
        barcodes_path = _find_sibling(parent, "barcodes.tsv")
        features_path = _find_sibling(parent, "features.tsv")
        if barcodes_path is None or features_path is None:
            # Older 10x layouts use genes.tsv instead of features.tsv
            features_path = _find_sibling(parent, "genes.tsv")
            if features_path is None:
                raise ReaderError(
                    f"Cannot find barcodes.tsv(.gz) or features.tsv(.gz) "
                    f"next to {path}"
                )

        # --- 1. Read sparse matrix
        with _open_maybe_gz(path) as fh:
            matrix = mmread(fh)
        matrix = matrix.tocsr()
        n_genes, n_cells = matrix.shape

        # --- 2. Read barcodes
        barcodes = _read_tsv_column(barcodes_path, col=0)
        if len(barcodes) != n_cells:
            raise ReaderError(
                f"barcodes has {len(barcodes)} rows but matrix has "
                f"{n_cells} columns"
            )

        # --- 3. Read features
        features_df = _read_tsv(features_path, n_cols=None)
        if features_df.shape[0] != n_genes:
            raise ReaderError(
                f"features has {features_df.shape[0]} rows but matrix has "
                f"{n_genes} rows"
            )
        gene_ids = features_df.iloc[:, 0].astype(str).tolist()
        gene_symbols = (
            features_df.iloc[:, 1].astype(str).tolist()
            if features_df.shape[1] > 1 else gene_ids
        )
        feature_types = (
            features_df.iloc[:, 2].astype(str).tolist()
            if features_df.shape[1] > 2 else None
        )
        genomes = (
            features_df.iloc[:, 3].astype(str).tolist()
            if features_df.shape[1] > 3 else None
        )

        # --- 4. Dense float32
        data = matrix.toarray().astype(np.float32)

        # --- 5. info
        info = {
            "missing_code": np.nan,
            "source_format": "mtx",
            "encoding": "count",
            "n_genes": int(n_genes),
            "n_cells": int(n_cells),
            "n_nonzero": int(matrix.nnz),
            "gene_ids": gene_ids,
            "gene_symbols": gene_symbols,
        }
        if feature_types is not None:
            info["feature_types"] = feature_types
        if genomes is not None:
            info["genomes"] = genomes

        return Form(
            data=data,
            dims=[gene_dim, cell_dim],
            labels={
                gene_dim: {g: i for i, g in enumerate(gene_ids)},
                cell_dim: {b: i for i, b in enumerate(barcodes)},
            },
            info=info,
        )


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #

def _open_maybe_gz(path: Path):
    """Open a file, transparently decompressing .gz."""
    if str(path).lower().endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def _find_sibling(parent: Path, stem: str) -> Path | None:
    """Return parent/stem or parent/stem.gz if it exists."""
    for name in (stem, stem + ".gz"):
        p = parent / name
        if p.exists():
            return p
    return None


def _read_tsv(path: Path, n_cols: int | None = None) -> pd.DataFrame:
    """Read a TSV, optionally limiting the number of columns."""
    with _open_maybe_gz(path) as fh:
        df = pd.read_csv(fh, sep="\t", header=None)
    if n_cols is not None:
        df = df.iloc[:, :n_cols]
    return df


def _read_tsv_column(path: Path, col: int) -> list[str]:
    """Read a single column from a TSV."""
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