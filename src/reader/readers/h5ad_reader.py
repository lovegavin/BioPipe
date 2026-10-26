# src/reader/readers/h5ad_reader.py
"""H5AD reader (AnnData).

Reads the main expression matrix and its two axes' identifiers from
an .h5ad file.

Layout:
    axis 0 = obs (cells), axis 1 = var (genes).

The matrix is read from ``adata.X`` unless ``args.layer`` names a
layer, in which case ``adata.layers[<name>]`` is used. Sparse
matrices are densified.

Cell and gene identifiers come from ``adata.obs.index`` and
``adata.var.index``.

H5AD internal compression is handled by h5py. External .gz/.bz2/.xz
wrappers are decompressed to a temporary disk file by the framework.

Label rules accepted:

    builtin           cell: obs.index
                      gene: var.index
    auto              position indices "0", "1", ...
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``builtin``. Duplicate labels are
disambiguated by appending ``#<position>``.

Reference
---------
AnnData: https://anndata.readthedocs.io/

Info fields set:

    missing_code      np.nan
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.core.contracts import reader_contract
from src.reader.readers._labels import unique_labels


class H5adReader(Reader):
    """Reader for .h5ad files."""
    parameters_schema = {'type': 'object',
     'properties': {'layer': {'type': ['string', 'null'],
                              'x-ui-type': 'string',
                              'title': 'Layer',
                              'description': 'Leave unset to read X.'}},
     'additionalProperties': True}
    dependencies = ['anndata>=0.10', 'h5py>=3.9']
    dependency_imports = ['anndata', 'h5py']

    output_contract = reader_contract()

    file_input = {'dims': ['sample', 'feature'], 'labels': {'sample': 'builtin', 'feature': 'builtin'}}

    extensions = [".h5ad"]
    handles_compression = False
    supports_disk_read = True
    disk_protocol = "dense-writer-v1"

    @staticmethod
    def _matrix(handle, args):
        key = "X" if args.get("layer") is None else "layers/" + str(args["layer"])
        if key not in handle:
            raise ReaderError(f"H5AD matrix {key!r} does not exist")
        return handle[key]

    def probe(self, path, **args):
        import h5py
        with h5py.File(path, "r") as handle:
            matrix = self._matrix(handle, args)
            shape = tuple(int(n) for n in (matrix.shape if isinstance(matrix, h5py.Dataset) else matrix.attrs["shape"]))
            if len(shape) != 2:
                raise ReaderError("H5AD matrix must have two axes")
            return {"file_bytes": Path(path).stat().st_size, "shape": shape,
                    "dtype": "float32", "dense_bytes": int(shape[0]) * int(shape[1]) * 4,
                    "preparation_bytes": int(shape[0]) * int(shape[1]) * (4 + (matrix["data"].dtype.itemsize if isinstance(matrix, h5py.Group) else 0))}

    def read_to_disk(self, path, dims, labels, writer, chunk_bytes, **args):
        import h5py
        from anndata.io import read_elem
        if len(dims) != 2:
            raise ReaderError("H5AD reader requires exactly two dims")
        with h5py.File(path, "r") as handle:
            matrix = self._matrix(handle, args)
            if isinstance(matrix, h5py.Dataset):
                width = max(1, chunk_bytes // max(8, matrix.dtype.itemsize * 2))
                for row in range(writer.shape[0]):
                    for column in range(0, writer.shape[1], width):
                        writer.write(row, column, matrix[row, column:column + width])
            else:
                encoding = matrix.attrs.get("encoding-type", "")
                if encoding not in ("csr_matrix", "csc_matrix"):
                    raise ReaderError(f"Unsupported H5AD sparse encoding: {encoding}")
                from src.reader.disk import accumulator
                with accumulator(writer, matrix["data"].dtype, chunk_bytes) as sums:
                    csr = encoding == "csr_matrix"
                    count = writer.shape[0 if csr else 1]
                    width = max(1, chunk_bytes // 32)
                    for major in range(count):
                        start, stop = map(int, matrix["indptr"][major:major + 2])
                        for offset in range(start, stop, width):
                            end = min(stop, offset + width)
                            indices = matrix["indices"][offset:end]
                            values = matrix["data"][offset:end]
                            for minor, value in zip(indices, values):
                                sums.add(major if csr else int(minor), int(minor) if csr else major, value)
            # Read only axis indexes, not all obs/var columns, layers or embeddings.
            indexes = []
            for axis in ("obs", "var"):
                group = handle[axis]
                indexes.append([str(v) for v in read_elem(group[group.attrs.get("_index", "_index")])])
            if tuple(map(len, indexes)) != writer.shape:
                raise ReaderError("H5AD axis indexes do not match matrix shape")
            return {"dims": list(dims), "labels": _resolve_labels(labels, *dims, *indexes),
                    "info": {"missing_code": np.nan}, "axis_info": {}}

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(
                f"H5AD reader requires exactly two dims, got {dims}"
            )
        obs_dim, var_dim = dims[0], dims[1]

        try:
            import anndata as ad
            from scipy.sparse import issparse
        except ImportError as exc:
            raise ReaderError(
                "anndata and scipy are required to read .h5ad files. "
                "Install with: pip install anndata scipy"
            ) from exc

        adata = ad.read_h5ad(str(path))

        layer = args.get("layer")
        if layer is None:
            X = adata.X
            source = "X"
        else:
            if layer not in adata.layers:
                raise ReaderError(
                    f"H5AD reader: layer '{layer}' not present. "
                    f"Available: {sorted(adata.layers)}"
                )
            X = adata.layers[layer]
            source = f"layers/{layer}"

        if X is None:
            raise ReaderError(
                f"H5AD file has no matrix in {source}: {path}"
            )

        if issparse(X):
            X = X.toarray()

        data = np.asarray(X, dtype=np.float32)

        obs_ids = [str(c) for c in adata.obs.index]
        var_ids = [str(g) for g in adata.var.index]

        n_obs, n_var = data.shape
        if len(obs_ids) != n_obs:
            raise ReaderError(
                f"obs has {len(obs_ids)} rows but X has {n_obs}"
            )
        if len(var_ids) != n_var:
            raise ReaderError(
                f"var has {len(var_ids)} rows but X has {n_var}"
            )

        final = _resolve_labels(
            labels, obs_dim, var_dim, obs_ids, var_ids
        )

        return Form(
            data=data,
            dims=list(dims),
            labels=final,
            info={"missing_code": np.nan},
        )


def _resolve_labels(labels, obs_dim, var_dim, obs_ids, var_ids):
    final: dict[str, dict[str, int]] = {}

    for dim_name, builtin in (
        (obs_dim, obs_ids),
        (var_dim, var_ids),
    ):
        rule = labels.get(dim_name, "builtin")

        if rule in (None, "builtin"):
            final[dim_name] = unique_labels(builtin, dim_name, "h5ad")
        elif rule == "auto":
            final[dim_name] = {
                str(i): i for i in range(len(builtin))
            }
        elif isinstance(rule, dict):
            final[dim_name] = {
                str(k): int(v) for k, v in rule.items()
            }
        else:
            raise ReaderError(
                f"H5AD reader: unsupported label rule for "
                f"'{dim_name}': {rule!r}"
            )

    return final
