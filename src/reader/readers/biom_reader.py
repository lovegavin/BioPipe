# src/reader/readers/biom_reader.py
"""BIOM reader for microbiome tables.

Supports BIOM 2.x JSON and HDF5 files. BIOM stores observations
(taxa) as rows and samples as columns; the matrix is returned as
(sample, taxon) so it composes naturally with metadata tables. The
``taxon`` axis keeps observation IDs (and optionally taxonomy strings).

BIOM's biological table is sparse. It is densified here because Loom-
like sparse disk preparation is not yet advertised by this Reader.
For very large tables a future disk protocol should be added rather
than silently raising memory pressure.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels


def _text(value):
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


class BiomReader(Reader):
    """Reader for .biom tables (JSON or HDF5)."""

    output_contract = reader_contract()
    dependencies = ["h5py>=3.9"]
    dependency_imports = ["h5py", "numpy"]

    file_input = {
        "dims": ["sample", "taxon"],
        "labels": {"sample": "builtin", "taxon": "builtin"},
    }
    extensions = [".biom"]
    parameters_schema = {
        "type": "object",
        "properties": {
            "taxonomy": {"type": "boolean", "default": False},
        },
        "additionalProperties": False,
    }

    @staticmethod
    def _from_json(path: Path):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("rows") or []
        columns = payload.get("columns") or []
        if not rows or not columns:
            raise ReaderError("BIOM JSON requires rows and columns")
        shape = payload.get("shape")
        n_rows, n_cols = len(rows), len(columns)
        if shape is not None and tuple(map(int, shape)) != (n_rows, n_cols):
            raise ReaderError("BIOM shape does not match rows/columns")
        data = np.zeros((n_rows, n_cols), dtype=np.float32)
        for entry in payload.get("data") or []:
            if len(entry) < 3:
                raise ReaderError("BIOM data entries must be [row, column, value]")
            row, column, value = int(entry[0]), int(entry[1]), float(entry[2])
            if not (0 <= row < n_rows and 0 <= column < n_cols):
                raise ReaderError("BIOM data index out of range")
            data[row, column] = value
        # BIOM stores observations (taxa) as rows and samples as columns.
        sample_ids = [str(col.get("id", i)) for i, col in enumerate(columns)]
        taxon_ids = [str(row.get("id", i)) for i, row in enumerate(rows)]
        taxonomy = [row.get("metadata", {}).get("taxonomy") for row in rows]
        return data.T, sample_ids, taxon_ids, taxonomy

    @staticmethod
    def _from_hdf5(path: Path):
        import h5py
        with h5py.File(path, "r") as handle:
            sample_group = handle["sample"]
            obs_group = handle["observation"]
            matrix = obs_group["matrix"]
            shape = tuple(int(n) for n in matrix.attrs.get("shape", handle.attrs.get("shape", ())))
            if len(shape) != 2:
                raise ReaderError("BIOM HDF5 group lacks a two-dimensional shape")
            # BIOM stores observation x sample sparse data.
            n_obs, n_samples = shape
            data = np.zeros((n_samples, n_obs), dtype=np.float32)
            indices = matrix["indices"]
            indptr = matrix["indptr"]
            values = matrix["data"]
            for obs in range(n_obs):
                start, stop = int(indptr[obs]), int(indptr[obs + 1])
                for pos in range(start, stop):
                    sample = int(indices[pos])
                    if not 0 <= sample < n_samples:
                        raise ReaderError("BIOM sample index out of range")
                    data[sample, obs] = float(values[pos])
            sample_ids = [_text(v) for v in sample_group["ids"][:]]
            taxon_ids = [_text(v) for v in obs_group["ids"][:]]
            taxonomy = None
            if "metadata" in obs_group:
                taxonomy = []
                for item in obs_group["metadata"][:]:
                    try:
                        taxonomy.append(json.loads(item).get("taxonomy"))
                    except (TypeError, ValueError, UnicodeDecodeError):
                        taxonomy.append(None)
        if len(sample_ids) != data.shape[0] or len(taxon_ids) != data.shape[1]:
            raise ReaderError("BIOM identifiers do not match matrix shape")
        return data, sample_ids, taxon_ids, taxonomy

    def _load(self, path: Path):
        path = Path(path)
        try:
            import h5py
            is_hdf5 = h5py.is_hdf5(path)
        except ImportError:
            is_hdf5 = False
        if is_hdf5:
            return self._from_hdf5(path)
        if path.suffix.lower() == ".biom":
            return self._from_json(path)
        raise ReaderError(f"Unrecognized BIOM file: {path}")

    def probe(self, path, **args):
        data, _, _, _ = self._load(path)
        return {
            "file_bytes": Path(path).stat().st_size,
            "shape": data.shape,
            "dtype": "float32",
            "dense_bytes": data.size * 4,
        }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"BIOM reader requires exactly two dims, got {dims}")
        sample_dim, taxon_dim = dims
        data, sample_ids, taxon_ids, taxonomy = self._load(path)
        if args.get("taxonomy") and any(taxonomy):
            taxon_ids = [
                str(t) if t is None else "; ".join(str(x) for x in t)
                for t in taxonomy
            ]

        def resolve(dim: str, builtin: list[str]):
            rule = labels.get(dim, "builtin")
            if rule in (None, "builtin"):
                return unique_labels(builtin, dim, "biom")
            if rule == "auto":
                return {str(i): i for i in range(len(builtin))}
            if isinstance(rule, dict):
                return {str(k): int(v) for k, v in rule.items()}
            raise ReaderError(f"BIOM reader: unsupported label rule for {dim!r}: {rule!r}")

        form = Form(
            data=data,
            dims=list(dims),
            labels={
                sample_dim: resolve(sample_dim, sample_ids),
                taxon_dim: resolve(taxon_dim, taxon_ids),
            },
            info={"missing_code": np.nan},
        )
        form.validate()
        return form
