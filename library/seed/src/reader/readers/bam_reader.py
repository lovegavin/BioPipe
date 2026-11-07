"""BAM alignment reader using pysam.

Output is one row per alignment and numeric alignment fields; read names
are kept as the row labels.  An index is not required for sequential reads.
"""
from __future__ import annotations

from pathlib import Path

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._bam_common import alignment_frame
from src.reader.readers._table_common import table_form


class BamReader(Reader):
    provider = 'operon-readers'
    """Binary Alignment/Map reader."""
    parameters_file = 'bam_reader.BamReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'BamReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Binary Alignment/Map reader',
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
     'dependencies': ['pysam'],
     'dependency_imports': ['pysam'],
     'description': 'Binary Alignment/Map reader.',
     'extensions': ['.bam'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['read', 'field'], 'labels': {'read': 'auto', 'field': 'builtin'}}}

    platforms = ["linux", "darwin"]

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"BAM reader requires exactly two dims, got {dims}")
        frame = alignment_frame(path, "BAM", int(args.get("max_records", 100000)))
        return table_form(
            frame.drop(columns=["qname"]), dims, labels, "BAM",
            encoders_cfg=args.get("encoders") or {},
            row_labels=frame["qname"].tolist(),
            info_extra={"format": "BAM"},
        )
