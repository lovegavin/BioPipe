"""HMMER3 tblout reader.

Reads the 18 fixed tblout fields and the free-text target description.
Comment lines beginning with '#' are skipped."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.reader.base import Reader
from src.reader.readers._table_common import table_form

FIELDS = [
    "target_name", "target_accession", "query_name", "query_accession",
    "full_evalue", "full_score", "full_bias", "best_evalue", "best_score",
    "best_bias", "exp", "reg", "clu", "ov", "env", "dom", "rep", "inc",
]


class HmmerTbloutReader(Reader):
    provider = 'operon-readers'
    """HMMER3 --tblout reader."""
    parameters_file = 'hmmer_tblout_reader.HmmerTbloutReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'HmmerTbloutReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'HMMER3 --tblout reader',
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
     'description': 'HMMER3 --tblout reader.',
     'extensions': ['.tblout'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['hit', 'field'], 'labels': {'hit': 'auto', 'field': 'builtin'}}}


    def read(self, path: Path, dims: list, labels: dict, **args):
        if len(dims) != 2:
            raise ReaderError(f"HMMER tblout reader requires exactly two dims, got {dims}")
        rows = []
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            if not line or line.startswith("#"):
                continue
            fields = line.split(maxsplit=18)
            if len(fields) < 18:
                raise ReaderError(f"HMMER tblout reader: expected at least 18 fields, got {len(fields)}")
            desc = fields[18] if len(fields) > 18 else ""
            rows.append(fields[:18] + [desc])
        if not rows:
            raise ReaderError("HMMER tblout reader: no hit rows")
        df = pd.DataFrame(rows, columns=FIELDS + ["description"])
        return table_form(df, dims, labels, "HMMER tblout", encoders_cfg=args.get("encoders") or {})
