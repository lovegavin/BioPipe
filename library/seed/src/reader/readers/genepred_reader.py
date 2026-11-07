"""UCSC genePred table reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


_GENEPRED_COLUMNS = [
    "name", "chrom", "strand", "tx_start", "tx_end", "cds_start", "cds_end",
    "exon_count", "exon_starts", "exon_ends",
]


class GenePredReader(Reader):
    provider = 'operon-readers'
    """UCSC genePred reader, one row per gene/transcript."""
    parameters_file = 'genepred_reader.GenePredReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'GenePredReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'UCSC genePred reader, one row per gene/transcript',
     'category': 'Data',
     'contracts': {'version': 1,
                   'inputs': [],
                   'output': {'version': 1,
                              'numeric': True,
                              'info': {'missing_code': {'type': ['number', 'null']},
                                       'encoders': {'type': 'object', 'optional': True}},
                              'dims': [],
                              'labels': [],
                              'parallel': [],
                              'ndim': 2,
                              'axis_fields': [],
                              'info_open': False}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False},
     'description': 'UCSC genePred reader, one row per gene/transcript.',
     'extensions': ['.genepred'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['gene', 'feature'], 'labels': {'gene': 'auto', 'feature': 'builtin'}}}


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
