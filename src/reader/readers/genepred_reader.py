"""UCSC genePred table reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


_GENEPRED_COLUMNS = [
    "name", "chrom", "strand", "tx_start", "tx_end", "cds_start", "cds_end",
    "exon_count", "exon_starts", "exon_ends",
]


class GenePredReader(Reader):
    """UCSC genePred reader, one row per gene/transcript."""

    output_contract = reader_contract()
    file_input = {"dims": ["gene", "feature"], "labels": {"gene": "auto", "feature": "builtin"}}
    extensions = [".genepred"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {"encoders": {"type": "object", "additionalProperties": True}},
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        try:
            frame = pd.read_csv(path, sep=r"\s+", header=None, comment="#")
        except Exception as exc:
            raise ReaderError(f"genePred reader: cannot parse {path}: {exc}") from exc
        if frame.shape[1] != 10:
            raise ReaderError(f"genePred reader: expected 10 columns, got {frame.shape[1]}")
        frame.columns = _GENEPRED_COLUMNS
        for column in ["tx_start", "tx_end", "cds_start", "cds_end", "exon_count"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        ids = frame["name"].astype(str).tolist()
        return table_form(
            frame.drop(columns=["name"]), dims, labels, "genePred",
            encoders_cfg=args.get("encoders") or {},
            row_labels=ids,
            info_extra={"format": "genePred", "n_genes": len(ids)},
        )
