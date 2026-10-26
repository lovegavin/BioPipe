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

Identifiers remain string axis labels, separate from the numeric count matrix.

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
    provider = 'biopipe-readers'
    parameters_file = 'mtx_reader.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'MtxReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'MtxReader',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'version': 1,
                              'numeric': True,
                              'info': {'missing_code': {'type': ['number', 'null']},
                                       'encoders': {'type': 'object', 'optional': True}},
                              'dims': [],
                              'labels': [],
                              'parallel': [],
                              'ndim': 2,
                              'axis_fields': [],
                              'info_open': False}},
     'resources': {'memory_modes': ['full', 'disk'],
                   'supports_cuda': False,
                   'disk_protocol': 'dense-writer-v1'},
     'extensions': ['.mtx'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': True,
     'file_input': {'dims': ['gene', 'cell'],
                    'labels': {'gene': 'builtin', 'cell': 'builtin'},
                    'compression': ['.gz'],
                    'companions': [['barcodes.tsv', 'barcodes.tsv.gz'],
                                   ['features.tsv', 'features.tsv.gz', 'genes.tsv', 'genes.tsv.gz']]}}





    def probe(self, path, **args):
        with _open_maybe_gz(Path(path)) as handle:
            _, _, shape, _ = _header(handle)
        return {"file_bytes": Path(path).stat().st_size, "shape": shape,
                "dtype": "float32", "dense_bytes": shape[0] * shape[1] * 4,
                "preparation_bytes": shape[0] * shape[1] * 12}

    def read_to_disk(self, path, dims, labels, writer, chunk_bytes, **args):
        if len(dims) != 2:
            raise ReaderError("MTX reader requires exactly two dims")
        path = Path(path)
        with _open_maybe_gz(path) as handle:
            field, symmetry, shape, nnz = _header(handle)
            if shape != writer.shape:
                raise ReaderError("MTX dimensions changed since inspection")
            from src.reader.disk import accumulator
            dtype = np.int64 if field in ('integer', 'pattern') else np.float64
            with accumulator(writer, dtype, chunk_bytes) as sums:
                seen = 0
                for line in handle:
                    if not line.strip() or line.lstrip().startswith("%"):
                        continue
                    parts = line.split()
                    if len(parts) != (2 if field == "pattern" else 3):
                        raise ReaderError("Invalid MatrixMarket coordinate")
                    row, column = int(parts[0]) - 1, int(parts[1]) - 1
                    value = 1 if field == "pattern" else int(parts[2]) if field == "integer" else float(parts[2])
                    sums.add(row, column, value)
                    if symmetry != "general" and row != column:
                        sums.add(column, row, -value if symmetry == "skew-symmetric" else value)
                    seen += 1
                    if seen > nnz:
                        raise ReaderError("MTX has more entries than declared")
                if seen != nnz:
                    raise ReaderError("MTX is truncated")
        barcodes = _find_sibling(path.parent, "barcodes.tsv")
        features = _find_sibling(path.parent, "features.tsv") or _find_sibling(path.parent, "genes.tsv")
        if barcodes is None or features is None:
            raise ReaderError("MTX requires barcodes.tsv and features.tsv/genes.tsv")
        indexes = [_read_tsv_column(features, 0), _read_tsv_column(barcodes, 0)]
        if tuple(map(len, indexes)) != shape:
            raise ReaderError("MTX axis labels do not match matrix shape")
        return {"dims": list(dims), "labels": {
            dim: _resolve_axis(labels.get(dim, "builtin"), values, dim, "mtx")
            for dim, values in zip(dims, indexes)}, "info": {"missing_code": np.nan}, "axis_info": {}}

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

        info: dict = {"missing_code": np.nan}

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


def _header(handle):
    header = handle.readline().strip().lower().split()
    if len(header) != 5 or header[:3] != ["%%matrixmarket", "matrix", "coordinate"]:
        raise ReaderError("Disk MTX reading requires MatrixMarket coordinate format")
    field, symmetry = header[3:]
    if field not in ("real", "integer", "pattern") or symmetry not in ("general", "symmetric", "skew-symmetric", "hermitian"):
        raise ReaderError("Unsupported MatrixMarket field or symmetry")
    for line in handle:
        if line.strip() and not line.lstrip().startswith("%"):
            rows, columns, nnz = map(int, line.split())
            if min(rows, columns, nnz) < 0 or (symmetry != "general" and rows != columns):
                raise ReaderError("Invalid MatrixMarket dimensions")
            return field, symmetry, (rows, columns), nnz
    raise ReaderError("Missing MatrixMarket dimensions")


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
            line = line.rstrip("\r\n")
            if not line.strip():
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
