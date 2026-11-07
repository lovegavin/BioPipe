"""InterProScan TSV reader (15 standard columns)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.reader.base import Reader
from src.reader.readers._table_common import table_form

FIELDS = [
    "protein_accession", "md5", "length", "analysis", "signature_accession",
    "signature_description", "start", "stop", "score", "status", "date",
    "interpro_accession", "interpro_description", "go_terms", "pathways",
]


class InterProScanReader(Reader):
    provider = 'operon-readers'
    """InterProScan tabular output reader."""
    parameters_file = 'interproscan_reader.InterProScanReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'InterProScanReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'InterProScan tabular output reader',
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
     'description': 'InterProScan tabular output reader.',
     'extensions': ['.iprscan'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['match', 'field'], 'labels': {'match': 'auto', 'field': 'builtin'}}}


    def read(self, path: Path, dims: list, labels: dict, **args):
        if len(dims) != 2:
            raise ReaderError(f"InterProScan reader requires exactly two dims, got {dims}")
        rows = []
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) < 15:
                raise ReaderError(f"InterProScan reader: expected 15 columns, got {len(fields)}")
            rows.append(fields[:15])
        if not rows:
            raise ReaderError("InterProScan reader: no match rows")
        df = pd.DataFrame(rows, columns=FIELDS)
        return table_form(df, dims, labels, "InterProScan", encoders_cfg=args.get("encoders") or {})
