"""BigWig interval reader using pyBigWig."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class BigWigReader(Reader):
    provider = 'operon-readers'
    """Reader for .bw / .bigwig coverage tracks."""
    parameters_file = 'bigwig_reader.BigWigReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'BigWigReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Reader for .bw / .bigwig coverage tracks',
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
     'dependencies': ['pyBigWig'],
     'dependency_imports': ['pyBigWig'],
     'description': 'Reader for .bw / .bigwig coverage tracks.',
     'extensions': ['.bw', '.bigwig'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['region', 'field'], 'labels': {'region': 'auto', 'field': 'builtin'}}}

    platforms = ["linux", "darwin"]

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"BigWig reader requires exactly two dims, got {dims}")
        try:
            import pyBigWig
        except ImportError as exc:
            raise ReaderError("BigWig reader requires pyBigWig") from exc
        max_records = int(args.get("max_records", 100000))
        if max_records < 1:
            raise ReaderError("BigWig reader: max_records must be >= 1")
        handle = pyBigWig.open(str(path))
        if handle is None:
            raise ReaderError(f"BigWig reader: cannot open {path}")
        try:
            chroms = handle.chroms()
            wanted = args.get("chrom")
            chosen = [wanted] if wanted else list(chroms)
            if wanted and wanted not in chroms:
                raise ReaderError(f"BigWig reader: chromosome {wanted!r} not present")
            rows = []
            names = []
            for chrom in chosen:
                if len(rows) >= max_records:
                    break
                intervals = handle.intervals(chrom) or ()
                for start, end, value in intervals:
                    if len(rows) >= max_records:
                        break
                    rows.append([chrom, int(start), int(end), float(value)])
                    names.append(f"{chrom}:{start}-{end}")
            if not rows:
                raise ReaderError("BigWig reader: no intervals")
            frame = pd.DataFrame(rows, columns=["chrom", "start", "end", "value"])
            return table_form(
                frame, dims, labels, "BigWig",
                encoders_cfg=args.get("encoders") or {},
                row_labels=names,
                info_extra={"format": "BigWig"},
            )
        finally:
            handle.close()
