"""NumPy array reader for .npy and .npz files."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.core.numeric import compact_numeric
from src.reader.base import Reader
from src.reader.readers._labels import unique_labels


class NpyReader(Reader):
    """Reader for 2D numeric .npy/.npz arrays; output is sample x feature."""

    output_contract = reader_contract()
    file_input = {"dims": ["sample", "feature"], "labels": {"sample": "auto", "feature": "auto"}}
    extensions = [".npz"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"key": {"type": "string"}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args):
        if len(dims) != 2:
            raise ReaderError(f"NumPy reader requires exactly two dims, got {dims}")
        path = Path(path)
        try:
            if path.suffix.lower() == ".npz":
                with np.load(path, allow_pickle=False) as bundle:
                    keys = list(bundle.keys())
                    key = args.get("key")
                    if key is None:
                        if len(keys) != 1:
                            raise ReaderError(
                                f"NumPy reader: .npz contains {len(keys)} arrays {keys}; specify 'key'"
                            )
                        key = keys[0]
                    if key not in bundle:
                        raise ReaderError(f"NumPy reader: key {key!r} not in {keys}")
                    array = bundle[key]
            else:
                array = np.load(path, allow_pickle=False)
        except OSError as exc:
            raise ReaderError(f"NumPy reader: cannot read {path}: {exc}") from exc
        if array.ndim != 2:
            raise ReaderError(f"NumPy reader: expected a 2D array, got ndim={array.ndim}")
        if not np.issubdtype(array.dtype, np.number):
            raise ReaderError(f"NumPy reader: expected numeric array, got {array.dtype}")
        data = compact_numeric(np.asarray(array, dtype=np.float64))
        final = {
            dims[0]: unique_labels([str(i) for i in range(data.shape[0])], dims[0], "npy"),
            dims[1]: unique_labels([str(i) for i in range(data.shape[1])], dims[1], "npy"),
        }
        return Form(data=data, dims=list(dims), labels=final, info={"missing_code": np.nan})
