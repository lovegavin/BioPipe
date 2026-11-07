"""PLINK BIM variant metadata reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class BimReader(Reader):
    provider = 'operon-readers'
    """PLINK BIM reader (six standard columns)."""
    parameters_file = 'bim_reader.BimReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'BimReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'PLINK BIM reader (six standard columns)',
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
     'description': 'PLINK BIM reader (six standard columns).',
     'extensions': ['.bim'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['variant', 'feature'],
                    'labels': {'variant': 'auto', 'feature': 'builtin'}}}


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
