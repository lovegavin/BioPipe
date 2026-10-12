# src/reader/readers/mtx_reader.py
"""MatrixMarket MTX reader (10x Genomics MEX format).

A MEX triplet:

    matrix.mtx      sparse count matrix (gene x cell)
    barcodes.tsv    cell barcodes (columns)
    features.tsv    gene features (rows), or genes.tsv in old layouts

The three files must live in the same directory. The reader is
triggered by pointing at the .mtx file. Each of the three may be
independently gzip-compressed; compression is detected by magic
bytes, not extension.

Per the 10x Genomics documentation, each element of the matrix is
the number of UMIs associated with a feature (row) and a barcode
(column). MatrixMarket coordinate format is 1-based.

The reader declares ``handles_compression = True`` because siblings
must be read from the original directory, not from a temporary file.

Label rules accepted:

    builtin           gene: features.tsv col 0
                      cell: barcodes.tsv
    auto              position indices "0", "1", ...
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``builtin``. Duplicate labels are
disambiguated by appending ``#<position>``.

Feature and barcode identifiers are used as labels directly. They
are not encoded: the row (or column) index of each entry in the
label map already identifies the position.

Reference
---------
10x Genomics MEX format:
https://support.10xgenomics.com/single-cell-gene-expression/software/pipelines/latest/output/matrices

Info fields set:

    missing_code      np.nan
"""

from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import mmread

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels


class MtxReader(Reader):
    """Reader for MatrixMarket .mtx files."""

    extensions = [".mtx"]
    handles_compression = True

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(
                f"MTX reader requires exactly two dims, got {dims}"
            )
        gene_dim, cell_dim = dims[0], dims[1]

        path = Path(path)
        parent = path.parent

        barcodes_path = _find_sibling(parent, "barcodes.tsv")
        features_path = _find_sibling(parent, "features.tsv")
        if features_path is None:
            features_path = _find_sibling(parent, "genes.tsv")
        if barcodes_path is None or features_path is None:
            raise ReaderError(
                f"Cannot find barcodes.tsv or features.tsv next to "
                f"{path}"
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
                f"features has {features_df.shape[0]} rows but matrix "
                f"has {n_genes} rows"
            )
        gene_ids = features_df.iloc[:, 0].astype(str).tolist()

        data = matrix.toarray().astype(np.float32)

        gene_rule = labels.get(gene_dim, "builtin")
        gene_labels = _resolve_axis(
            gene_rule, gene_ids, gene_dim, "mtx"
        )

        cell_rule = labels.get(cell_dim, "builtin")
        cell_labels = _resolve_axis(
            cell_rule, barcodes, cell_dim, "mtx"
        )

        final: dict[str, dict[str, int]] = {
            gene_dim: gene_labels,
            cell_dim: cell_labels,
        }

        return Form(
            data=data,
            dims=list(dims),
            labels=final,
            info={"missing_code": np.nan},
        )


def _open_maybe_gz(path: Path):
    with open(path, "rb") as fh:
        magic = fh.read(2)
    if magic == b"\x1f\x8b":
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


def _resolve_axis(rule, builtin_values, dim_name, source):
    if rule in (None, "builtin"):
        return unique_labels(builtin_values, dim_name, source)
    if rule == "auto":
        return {str(i): i for i in range(len(builtin_values))}
    if isinstance(rule, dict):
        return {str(k): int(v) for k, v in rule.items()}
    raise ReaderError(
        f"MTX reader: unsupported label rule for "
        f"'{dim_name}': {rule!r}"
    )