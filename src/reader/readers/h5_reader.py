"""Generic HDF5 2D dataset reader."""
from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.core.numeric import compact_numeric
from src.reader.base import Reader


class H5Reader(Reader):
    """Read a 2D numeric dataset from an .hdf5 file."""

    output_contract = reader_contract()
    file_input = {"dims": ["sample", "feature"], "labels": {"sample": "auto", "feature": "auto"}}
    extensions = [".hdf5"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "dataset": {"type": ["string", "null"], "default": None},
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"HDF5 reader requires exactly two dims, got {dims}")
        sample_dim, feature_dim = dims
        wanted = args.get("dataset") or None
        with h5py.File(path, "r") as fh:
            if wanted:
                if wanted not in fh:
                    raise ReaderError(f"HDF5 reader: dataset {wanted!r} not found")
                ds = fh[wanted]
                if not isinstance(ds, h5py.Dataset) or ds.ndim != 2:
                    raise ReaderError(f"HDF5 reader: {wanted!r} is not a 2D dataset")
                data = np.asarray(ds)
            else:
                candidates = []
                def visit(name, obj):
                    if isinstance(obj, h5py.Dataset) and obj.ndim == 2 and obj.dtype.kind in "fiu":
                        candidates.append((obj.size, name, obj))
                fh.visititems(visit)
                if not candidates:
                    raise ReaderError("HDF5 reader: no 2D numeric dataset found")
                _, wanted, ds = max(candidates, key=lambda item: item[0])
                data = np.asarray(ds)
        dataset_name = "/" + str(wanted).lstrip("/")
        if data.shape[0] == 0 or data.shape[1] == 0:
            raise ReaderError("HDF5 reader: dataset is empty")
        n_samples, n_features = data.shape
        return Form(
            data=compact_numeric(data.astype(np.float64)),
            dims=[sample_dim, feature_dim],
            labels={
                sample_dim: {str(i): i for i in range(n_samples)},
                feature_dim: {str(i): i for i in range(n_features)},
            },
            info={"missing_code": np.nan, "dataset": dataset_name},
        )
