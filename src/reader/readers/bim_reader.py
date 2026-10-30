"""PLINK BIM variant metadata reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class BimReader(Reader):
    """PLINK BIM reader (six standard columns)."""

    output_contract = reader_contract()
    file_input = {"dims": ["variant", "feature"], "labels": {"variant": "auto", "feature": "builtin"}}
    extensions = [".bim"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "encoders": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        try:
            frame = pd.read_csv(path, sep=r"\s+", header=None, comment="#")
        except Exception as exc:
            raise ReaderError(f"BIM reader: cannot parse {path}: {exc}") from exc
        if frame.shape[1] != 6:
            raise ReaderError(f"BIM reader: expected 6 columns, got {frame.shape[1]}")
        frame.columns = ["chrom", "variant", "cm", "pos", "alt", "ref"]
        ids = frame["variant"].astype(str).tolist()
        frame["pos"] = pd.to_numeric(frame["pos"], errors="coerce")
        frame["cm"] = pd.to_numeric(frame["cm"], errors="coerce")
        return table_form(
            frame.drop(columns=["variant"]), dims, labels, "BIM",
            encoders_cfg=args.get("encoders") or {},
            row_labels=ids,
            info_extra={"format": "BIM", "n_variants": len(ids)},
        )
