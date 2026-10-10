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

Non-numeric identifiers are encoded. The encoder instance used for
each axis is recorded in ``info["encoders"]``.

Reference
---------
10x Genomics MEX format:
https://support.10xgenomics.com/single-cell-gene-expression/software/pipelines/latest/output/matrices

Info fields set:

    missing_code      np.nan
    encoders          present only when an axis was encoded
"""

from __future__ import annotations

import gzip
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.io import mmread

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._encoder import get_encoder
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

        encoders_cfg = args.get("encoders", {})

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

        encoders_used: dict[str, dict[str, object]] = {}

        gene_rule = labels.get(gene_dim, "builtin")
        gene_labels, gene_encs = _resolve_axis(
            gene_rule, gene_ids, gene_dim, encoders_cfg, "mtx"
        )
        if gene_encs:
            encoders_used[gene_dim] = gene_encs

        cell_rule = labels.get(cell_dim, "builtin")
        cell_labels, cell_encs = _resolve_axis(
            cell_rule, barcodes, cell_dim, encoders_cfg, "mtx"
        )
        if cell_encs:
            encoders_used[cell_dim] = cell_encs

        final: dict[str, dict[str, int]] = {
            gene_dim: gene_labels,
            cell_dim: cell_labels,
        }

        info: dict = {"missing_code": np.nan}
        if encoders_used:
            info["encoders"] = encoders_used

        return Form(
            data=data,
            dims=list(dims),
            labels=final,
            info=info,
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


def _resolve_axis(rule, builtin_values, dim_name,
                  encoders_cfg, source):
    if rule in (None, "builtin"):
        return _encode_labels(
            builtin_values, dim_name, encoders_cfg, source
        )
    if rule == "auto":
        return {str(i): i for i in range(len(builtin_values))}, {}
    if isinstance(rule, dict):
        return {str(k): int(v) for k, v in rule.items()}, {}
    raise ReaderError(
        f"MTX reader: unsupported label rule for "
        f"'{dim_name}': {rule!r}"
    )


def _encode_labels(values, dim_name, encoders_cfg, source):
    try:
        _ = np.asarray(values, dtype=np.float32)
        return unique_labels(values, dim_name, source), {}
    except (ValueError, TypeError):
        pass

    enc_name = encoders_cfg.get("all", "labelencoder")
    encoder = get_encoder(enc_name)
    codes = encoder.fit_transform(values)
    labels_map = unique_labels(values, dim_name, source)
    return labels_map, {dim_name: encoder}