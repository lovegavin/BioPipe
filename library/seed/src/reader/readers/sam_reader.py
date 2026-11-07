"""SAM text reader.

Reads the 11 mandatory SAM fields and skips @ header lines.
Binary BAM/CRAM files are not handled by this reader."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class SamReader(Reader):
    provider = 'operon-readers'
    """Sequence Alignment/Map text reader."""
    parameters_file = 'sam_reader.SamReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'SamReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Sequence Alignment/Map text reader',
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
     'description': 'Sequence Alignment/Map text reader.',
     'extensions': ['.sam'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['region', 'field'], 'labels': {'region': 'auto', 'field': 'builtin'}}}


    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"SAM reader requires exactly two dims, got {dims}")
        df = rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line or line.startswith("@"):
                continue
            parts = line.split("\t")
            if len(parts) < 11:
                raise ReaderError(f"SAM reader: expected at least 11 columns, got {len(parts)}")
            rows.append(parts[:11])
        if not rows:
            raise ReaderError("SAM reader: no alignment records")
        df = pd.DataFrame(rows, columns=[
            "qname", "flag", "rname", "pos", "mapq", "cigar", "rnext", "pnext",
            "tlen", "seq", "qual"])
        return table_form(
            df, dims, labels, "SAM",
            encoders_cfg=args.get("encoders") or {},
        )
