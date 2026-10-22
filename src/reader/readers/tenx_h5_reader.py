"""10x Genomics Cell Ranger HDF5 count matrix reader.

Reads ``filtered_feature_bc_matrix.h5`` (also
``raw_feature_bc_matrix.h5``) produced by Cell Ranger 3.0+. The
file is an HDF5 container with a sparse CSC feature x cell count
matrix and per-feature metadata (name, id, feature_type, genome).

Layout:
    axis 0 = feature
    axis 1 = cell

The ``filtered_feature_bc_matrix.h5`` from a CITE-seq experiment
holds both gene expression features and antibody capture features.
Read the two separately with ``feature_type``:

    feature_type: "Gene Expression"    -> genes x cells
    feature_type: "Antibody Capture"   -> antibodies x cells

Omitting ``feature_type`` returns every feature in a single matrix.

Label rules accepted:

    builtin           feature: gene symbol or antibody name
                                (or Ensembl id / antibody id with
                                ``feature_id_field='id'``)
                      cell:    10x barcode
    auto              position indices "0", "1", ...
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``builtin``. Duplicate labels are
disambiguated by appending ``#<position>``.

Info fields set:

    missing_code      np.nan
    representation    "counts"
    feature_types     per-feature Cell Ranger feature_type string
    genome            per-feature genome name ("" when absent)

``feature_types`` and ``genome`` are declared axis-parallel to the
feature axis in ``axis_info``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels


class TenxH5Reader(Reader):
    """Reader for 10x Cell Ranger h5 count matrices."""

    extensions = [".h5"]
    handles_compression = False
    dependencies = ["h5py>=3.0", "scipy>=1.10"]
    dependency_imports = ["h5py", "scipy"]
    output_contract = reader_contract(extra={
        "representation": {"type": "string", "const": "counts"},
        "feature_types": {"type": "array", "items": "string"},
        "genome": {"type": "array", "items": "string"},
    })
    file_input = {
        "dims": ["feature", "cell"],
        "labels": {"feature": "builtin", "cell": "builtin"},
        "compression": [],
        "companions": [],
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_type": {"type": "string"},
            "feature_id_field": {
                "type": "string",
                "enum": ["name", "id"],
                "default": "name",
            },
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(
                f"tenx_h5 reader requires exactly two dims, got {dims}"
            )
        feature_dim, cell_dim = dims

        feature_type_filter = args.get("feature_type")
        id_field = args.get("feature_id_field", "name")
        if id_field not in ("name", "id"):
            raise ReaderError(
                f"tenx_h5: feature_id_field must be 'name' or 'id', "
                f"got {id_field!r}"
            )

        try:
            import h5py
            from scipy.sparse import csc_matrix
        except ImportError as exc:
            raise ReaderError(
                "tenx_h5: h5py and scipy are required. "
                "Install with: pip install h5py scipy"
            ) from exc

        try:
            with h5py.File(str(path), "r") as f:
                if "matrix" not in f:
                    raise ReaderError(
                        f"tenx_h5: {path} is not a 10x Cell Ranger "
                        f"matrix (missing top-level 'matrix' group)"
                    )
                m = f["matrix"]
                for key in ("shape", "data", "indices", "indptr",
                            "barcodes", "features"):
                    if key not in m:
                        raise ReaderError(
                            f"tenx_h5: {path} is missing matrix/{key}"
                        )
                shape = tuple(int(x) for x in m["shape"][:])
                n_features, n_cells = shape
                data = m["data"][:]
                indices = m["indices"][:]
                indptr = m["indptr"][:]
                barcodes = [
                    b.decode() if isinstance(b, bytes) else str(b)
                    for b in m["barcodes"][:]
                ]
                feature_group = m["features"]
                for key in ("feature_type", "name", "id"):
                    if key not in feature_group:
                        raise ReaderError(
                            f"tenx_h5: {path} is missing "
                            f"matrix/features/{key}"
                        )
                feature_types = [
                    s.decode() if isinstance(s, bytes) else str(s)
                    for s in feature_group["feature_type"][:]
                ]
                feature_names = [
                    s.decode() if isinstance(s, bytes) else str(s)
                    for s in feature_group["name"][:]
                ]
                feature_ids = [
                    s.decode() if isinstance(s, bytes) else str(s)
                    for s in feature_group["id"][:]
                ]
                if "genome" in feature_group:
                    genomes = [
                        s.decode() if isinstance(s, bytes) else str(s)
                        for s in feature_group["genome"][:]
                    ]
                else:
                    genomes = ["" for _ in range(n_features)]
        except OSError as exc:
            raise ReaderError(
                f"tenx_h5: cannot open {path}: {exc}"
            ) from exc

        if len(barcodes) != n_cells:
            raise ReaderError(
                f"tenx_h5: barcode count {len(barcodes)} != "
                f"cell count {n_cells}"
            )
        if not (len(feature_types) == len(feature_names)
                == len(feature_ids) == len(genomes) == n_features):
            raise ReaderError(
                f"tenx_h5: feature metadata lengths do not match "
                f"feature count {n_features}"
            )

        if feature_type_filter is not None:
            keep = [
                i for i, t in enumerate(feature_types)
                if t == feature_type_filter
            ]
            if not keep:
                available = sorted(set(feature_types))
                raise ReaderError(
                    f"tenx_h5: no features with feature_type="
                    f"{feature_type_filter!r}. Available: {available}"
                )
        else:
            keep = list(range(n_features))

        mat = csc_matrix(
            (data, indices, indptr), shape=(n_features, n_cells),
        )
        selected = mat[keep, :].toarray().astype(np.float32)

        feature_labels = feature_names if id_field == "name" else feature_ids
        selected_feature_labels = [feature_labels[i] for i in keep]
        selected_types = [feature_types[i] for i in keep]
        selected_genomes = [genomes[i] for i in keep]

        final: dict[str, dict[str, int]] = {}
        for dim_name, builtin_values in (
            (feature_dim, selected_feature_labels),
            (cell_dim, barcodes),
        ):
            rule = labels.get(dim_name, "builtin")
            if rule in (None, "builtin"):
                final[dim_name] = unique_labels(
                    builtin_values, dim_name, "tenx_h5"
                )
            elif rule == "auto":
                final[dim_name] = {
                    str(i): i for i in range(len(builtin_values))
                }
            elif isinstance(rule, dict):
                final[dim_name] = {
                    str(k): int(v) for k, v in rule.items()
                }
            else:
                raise ReaderError(
                    f"tenx_h5 reader: unsupported label rule for "
                    f"'{dim_name}': {rule!r}"
                )

        return Form(
            data=selected,
            dims=list(dims),
            labels=final,
            info={
                "missing_code": np.nan,
                "representation": "counts",
                "feature_types": selected_types,
                "genome": selected_genomes,
            },
            axis_info={feature_dim: ["feature_types", "genome"]},
        )
