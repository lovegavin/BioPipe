"""ENCODE bedMethyl reader (standard 15 columns)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import ReaderError
from src.reader.base import Reader
from src.reader.readers._table_common import table_form

FIELDS = [
    "chrom", "start", "end", "name", "score", "strand", "thick_start",
    "thick_end", "item_rgb", "coverage", "freq_c", "freq_t", "freq_g",
    "freq_a", "freq_n",
]


class BedMethylReader(Reader):
    provider = 'operon-readers'
    """bedMethyl reader (15-column ENCODE layout)."""
    parameters_file = 'bedmethyl_reader.BedMethylReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'BedMethylReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'bedMethyl reader (15-column ENCODE layout)',
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
     'description': 'bedMethyl reader (15-column ENCODE layout).',
     'extensions': ['.bedmethyl'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['region', 'field'], 'labels': {'region': 'auto', 'field': 'builtin'}}}


    def read(self, path: Path, dims: list, labels: dict, **args):
        if len(dims) != 2:
            raise ReaderError(f"bedMethyl reader requires exactly two dims, got {dims}")
        rows = []
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) < 15:
                raise ReaderError(f"bedMethyl reader: expected 15 columns, got {len(fields)}")
            rows.append(fields[:15])
        if not rows:
            raise ReaderError("bedMethyl reader: no regions")
        df = pd.DataFrame(rows, columns=FIELDS)
        return table_form(df, dims, labels, "bedMethyl", encoders_cfg=args.get("encoders") or {})
