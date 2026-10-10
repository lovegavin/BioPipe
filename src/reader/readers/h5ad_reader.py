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

H5AD is an HDF5 container; compression is handled internally by
h5py and is not the framework's concern.

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
from src.reader.readers._labels import unique_labels


class H5adReader(Reader):
    """Reader for .h5ad files."""

    extensions = [".h5ad"]
    handles_compression = True

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