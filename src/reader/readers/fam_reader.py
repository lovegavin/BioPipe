"""PLINK FAM sample metadata reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class FamReader(Reader):
    """PLINK FAM reader (six standard columns)."""

    output_contract = reader_contract()
    file_input = {"dims": ["sample", "feature"], "labels": {"sample": "auto", "feature": "builtin"}}
    extensions = [".fam"]
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
            raise ReaderError(f"FAM reader: cannot parse {path}: {exc}") from exc
        if frame.shape[1] != 6:
            raise ReaderError(f"FAM reader: expected 6 columns, got {frame.shape[1]}")
        frame.columns = ["family", "individual", "father", "mother", "sex", "phenotype"]
        ids = frame["individual"].astype(str).tolist()
        frame["sex"] = pd.to_numeric(frame["sex"], errors="coerce").mask(lambda s: s <= 0)
        frame["phenotype"] = pd.to_numeric(frame["phenotype"], errors="coerce").mask(lambda s: s <= 0)
        return table_form(
            frame.drop(columns=["individual"]), dims, labels, "FAM",
            encoders_cfg=args.get("encoders") or {},
            row_labels=ids,
            info_extra={"format": "FAM", "n_samples": len(ids)},
        )
