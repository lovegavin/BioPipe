"""HapMap genotype table reader."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class HapmapReader(Reader):
    """HapMap genotype table, returned as variant x sample dosage."""

    output_contract = reader_contract()
    file_input = {"dims": ["variant", "sample"], "labels": {"variant": "auto", "sample": "auto"}}
    extensions = [".hapmap"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
            "has_header": {"type": "boolean", "default": True},
            "id_column": {"type": "integer", "minimum": 0, "default": 0},
            "first_sample_column": {"type": "integer", "minimum": 0, "default": 10},
            "encoders": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        try:
            frame = pd.read_csv(path, sep=r"\s+", header=None)
        except Exception as exc:
            raise ReaderError(f"HapMap reader: cannot parse {path}: {exc}") from exc
        if frame.shape[0] == 0:
            raise ReaderError("HapMap reader: empty table")
        has_header = bool(args.get("has_header", True))
        id_col = int(args.get("id_column", 0))
        first_sample = int(args.get("first_sample_column", 10))
        if has_header:
            header = [str(v).strip() for v in frame.iloc[0].tolist()]
            frame = frame.iloc[1:].reset_index(drop=True)
        else:
            header = [f"c{i}" for i in range(frame.shape[1])]
        if id_col >= len(header) or first_sample > len(header):
            raise ReaderError("HapMap reader: id_column/first_sample_column out of range")
        sample_ids = header[first_sample:]
        if not sample_ids:
            raise ReaderError("HapMap reader: no sample genotype columns")
        variants = frame.iloc[:, id_col].astype(str).tolist()
        gt = frame.iloc[:, first_sample:].astype(str)
        data = np.full((len(frame), len(sample_ids)), np.nan, dtype=np.float64)
        for i in range(len(frame)):
            row = gt.iloc[i].tolist()
            ref = None
            for value in row:
                text = str(value).strip()
                if len(text) == 2 and "N" not in text.upper() and "-" not in text:
                    ref = text[0]
                    break
            if ref is None:
                continue
            for j, value in enumerate(row):
                text = str(value).strip()
                if len(text) != 2 or "N" in text.upper() or "-" in text:
                    continue
                data[i, j] = float((text[0] != ref) + (text[1] != ref))
        df = pd.DataFrame(data, columns=sample_ids)
        return table_form(
            df, dims, labels, "HapMap",
            encoders_cfg=args.get("encoders") or {},
            row_labels=variants,
            info_extra={"format": "HapMap", "genotype_encoding": "non_reference_allele_count"},
        )
