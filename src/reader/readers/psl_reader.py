"""UCSC PSL alignment table reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


_PSL_COLUMNS = [
    "matches", "mis_matches", "rep_matches", "n_count", "q_num_insert",
    "q_base_insert", "t_num_insert", "t_base_insert", "strand", "q_name",
    "q_size", "q_start", "q_end", "t_name", "t_size", "t_start", "t_end",
    "block_count", "block_sizes", "q_starts", "t_starts",
]


class PslReader(Reader):
    """UCSC PSL reader, one row per alignment."""

    output_contract = reader_contract()
    file_input = {"dims": ["alignment", "feature"], "labels": {"alignment": "auto", "feature": "builtin"}}
    extensions = [".psl"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        try:
            frame = pd.read_csv(path, sep="\t", header=None, comment="#")
        except Exception as exc:
            raise ReaderError(f"PSL reader: cannot parse {path}: {exc}") from exc
        if frame.shape[1] != 21:
            raise ReaderError(f"PSL reader: expected 21 columns, got {frame.shape[1]}")
        frame.columns = _PSL_COLUMNS
        for column in _PSL_COLUMNS[:9] + _PSL_COLUMNS[10:18]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return table_form(
            frame, dims, labels, "PSL",
            encoders_cfg=args.get("encoders") or {},
            row_labels=[f"alignment:{i}" for i in range(len(frame))],
            info_extra={"format": "PSL", "n_alignments": len(frame)},
        )
