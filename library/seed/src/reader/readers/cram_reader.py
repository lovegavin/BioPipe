"""CRAM alignment reader using pysam.

A reference FASTA must be supplied as ``reference`` because CRAM stores
alignments relative to a reference sequence.
"""
from __future__ import annotations

from pathlib import Path

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.reader.readers._bam_common import alignment_frame
from src.reader.readers._table_common import table_form


class CramReader(Reader):
    provider = 'operon-readers'
    """Compressed Reference-oriented Alignment/Map reader."""
    parameters_file = 'cram_reader.CramReader.parameters.json'
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        'protocol_version': 3,
     'id': 'CramReader',
     'version': '1.0.0',
     'kind': 'reader',
     'title': 'Compressed Reference-oriented Alignment/Map reader',
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
     'description': 'Compressed Reference-oriented Alignment/Map reader.',
     'extensions': ['.cram'],
     'requires_siblings': [],
     'excludes_siblings': [],
     'handles_compression': False,
     'file_input': {'dims': ['read', 'field'], 'labels': {'read': 'auto', 'field': 'builtin'}}}

    platforms = ["linux", "darwin"]

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"CRAM reader requires exactly two dims, got {dims}")
        reference = args.get("reference")
        frame = alignment_frame(path, "CRAM", int(args.get("max_records", 100000)), reference=reference)
        return table_form(
            frame.drop(columns=["qname"]), dims, labels, "CRAM",
            encoders_cfg=args.get("encoders") or {},
            row_labels=frame["qname"].tolist(),
            info_extra={"format": "CRAM", "reference": str(reference)},
        )
